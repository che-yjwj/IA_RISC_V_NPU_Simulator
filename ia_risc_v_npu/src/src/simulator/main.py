from __future__ import annotations

import logging
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Union

import numpy as np

# Ensure repository root is on sys.path when executed directly.
if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from src.cq import (
    CommandQueue,
    CQDispatcher,
    ISASpec,
    build_execution_plan,
    load_isa_spec,
)
from src.npu.cluster import ClusterPolicy, ClusterTask, NPUCluster
from src.npu.model import NPU
from src.risc_v.engine import (
    WORD_SIZE_BYTES,
    BranchPredictorConfig,
    ExecutionTimingConfig,
    RISCVEngine,
)
from src.simulator.config import (
    DEFAULT_L1_CONFIG,
    DEFAULT_L2_CONFIG,
    default_simulator_config,
)
from src.simulator.determinism import (
    DeterminismConfig,
    configure_deterministic_environment,
)
from src.simulator.devices import SPM, Bus
from src.simulator.events import EventScheduler
from src.simulator.identifiers import (
    DRAM as DRAM_REGION,
)
from src.simulator.identifiers import (
    MMIO as MMIO_REGION,
)
from src.simulator.identifiers import (
    SPM as SPM_REGION,
)
from src.simulator.identifiers import (
    BusMasterID,
)
from src.simulator.memory import MemorySystem
from src.simulator.mmio import MMIO
from src.simulator.models import CacheConfig, DRAMConfig
from src.simulator.program import ProgramImage, ProgramSegment


@dataclass(slots=True)
class SimulationReport:
    cycles: int
    instructions: int
    halted: bool
    reason: str
    sim_time: int
    elapsed_seconds: float
    memory_report: Dict[str, Any]
    stall_breakdown: Dict[str, float | int]
    npu_metrics: Dict[str, float | int]
    fetch_metrics: Dict[str, float | int]

    @property
    def mips(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return (self.instructions / 1_000_000) / self.elapsed_seconds


MIN_EVENT_DELAY = 1


class AdaptiveSimulator:
    """Primary integration point for CPU, NPU, and shared memory models."""

    def __init__(
        self,
        *,
        config: Optional[Mapping[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self._config = (
            deepcopy(config) if config is not None else default_simulator_config()
        )

        determinism = self._build_determinism_config()
        configure_deterministic_environment(
            seed=determinism.seed,
            logger=self.logger,
            config=determinism,
        )

        bus_kwargs = self._build_bus_config()
        self.bus = Bus(**bus_kwargs, logger=self.logger.getChild("bus"))
        self.dram = bytearray(DRAM_REGION.size)
        self.spm = SPM(SPM_REGION.size // 1024)
        self.npu = NPU()

        cache_cfg = self._get_config_section("cache")
        l1_config = self._build_cache_config(
            "L1", cache_cfg.get("l1"), DEFAULT_L1_CONFIG
        )
        l2_config = self._build_cache_config(
            "L2", cache_cfg.get("l2"), DEFAULT_L2_CONFIG
        )

        dram_cfg = self._build_dram_config(self._get_config_section("dram"))
        self.npu_cluster = NPUCluster(
            self.bus,
            cores=int(self._resolve_npu_cores()),
            dma_master_id=int(BusMasterID.NPU_DMA),
            policy=self._resolve_npu_policy(),
            compute_engine=self.npu,
            logger=self.logger.getChild("npu"),
        )
        self.mmio = MMIO(self.npu_cluster)
        self.memory_system = MemorySystem(
            self.bus,
            dram_config=dram_cfg,
            l1_config=l1_config,
            l2_config=l2_config,
            logger=self.logger.getChild("memory"),
        )

        # Connect devices to the bus
        self.bus.add_device(
            DRAM_REGION.name, self.dram, DRAM_REGION.base, DRAM_REGION.end
        )
        self.bus.add_device(
            SPM_REGION.name,
            self.spm,
            SPM_REGION.base,
            SPM_REGION.end,
        )
        self.bus.add_device(
            MMIO_REGION.name,
            self.mmio,
            MMIO_REGION.base,
            MMIO_REGION.end,
        )

        self.risc_v_engine = RISCVEngine(
            self.bus,
            self.memory_system,
            master_id=int(BusMasterID.CPU),
            branch_config=self._build_branch_config(),
            execution_timing=self._build_execution_config(),
        )
        self.scheduler: Optional[EventScheduler] = None
        # self.event_system = EventBasedSystem() # This will be implemented later
        # self.fidelity_controller = FidelityController()  # TODO: implement
        self.halt = False
        self.sim_time = 0
        self._fetch_stats = {
            "fetches": 0,
            "misses": 0,
            "total_latency": 0,
            "total_penalty": 0,
        }
        self._fetch_hit_latency = self.memory_system.front_hit_latency()
        # CQ execution bookkeeping
        self._cq_initial_data: Dict[str, np.ndarray] = {}
        self._cq_dram_allocations: Dict[str, Dict[str, Any]] = {}
        self._cq_spm_allocations: Dict[str, Dict[str, Any]] = {}
        self._cq_next_dram_addr = DRAM_REGION.base
        self._cq_next_spm_offset = 0
        self._cq_dma_bytes = 0
        self._cq_gemm_cycle_log: list[int] = []

    def _reset_cq_runtime(self) -> None:
        self._cq_dram_allocations.clear()
        self._cq_spm_allocations.clear()
        self._cq_next_dram_addr = DRAM_REGION.base
        self._cq_next_spm_offset = 0
        self._cq_dma_bytes = 0
        self._cq_gemm_cycle_log = []

    def load_cq_tensors(self, tensors: Mapping[str, Any]) -> None:
        """Register initial tensor contents for CQ URIs.

        Payload values can be numpy arrays or dictionaries with `shape` and
        `values` (flat list)."""

        for uri, payload in tensors.items():
            data = self._coerce_tensor_payload(payload)
            self._cq_initial_data[uri] = data

    def _coerce_tensor_payload(self, payload: Any) -> np.ndarray:
        if isinstance(payload, np.ndarray):
            if payload.dtype != np.float32:
                return payload.astype(np.float32)
            return payload
        if isinstance(payload, Mapping):
            shape = payload.get("shape")
            values = payload.get("values")
            if shape is None or values is None:
                raise ValueError("Tensor mapping payload requires 'shape' and 'values'")
            array = np.array(values, dtype=np.float32)
            array = array.reshape(tuple(int(dim) for dim in shape))
            return array
        raise TypeError("Unsupported tensor payload type; expected ndarray or mapping")

    def run_cq_trace(
        self,
        queue: CommandQueue,
        *,
        isa_spec: ISASpec | None = None,
    ) -> dict[str, Any]:
        """Execute a CQ trace via the dispatcher scaffold and return summary data."""

        self._reset_cq_runtime()
        spec = isa_spec or load_isa_spec()
        plan = build_execution_plan(queue, spec)
        dispatcher = CQDispatcher()
        outcome = dispatcher.run(queue)

        action_lookup: Dict[str, dict[str, Any]] = {}
        for dma in plan.dma_ops:
            action_lookup[dma.cmd_id] = {
                "type": "dma",
                "cmd_id": dma.cmd_id,
                "src": dma.src,
                "dst": dma.dst,
                "shape": dma.shape,
                "strides": dma.strides,
            }
        for gemm in plan.gemm_ops:
            action_lookup[gemm.cmd_id] = {
                "type": "gemm",
                "cmd_id": gemm.cmd_id,
                "m": gemm.m,
                "n": gemm.n,
                "k": gemm.k,
                "inputs": {"a": gemm.a, "b": gemm.b},
                "output": gemm.c,
            }
        for fence in plan.fence_ops:
            action_lookup[fence.cmd_id] = {
                "type": "fence",
                "cmd_id": fence.cmd_id,
                "target": fence.target,
            }

        actions: list[dict[str, Any]] = []
        for command in queue:
            action = action_lookup.get(command.cmd_id)
            if action is not None:
                actions.append(action)

        execution_report = self._execute_cq_actions(actions)

        dispatch_summary = {
            "executed": outcome.commands_executed,
            "completed": list(outcome.trace.completed),
            "rejected": list(outcome.trace.rejected),
            "queue_wait": {
                "average": outcome.stats.average_queue_wait,
                "max": outcome.stats.max_queue_wait,
                "total": outcome.stats.total_queue_wait,
                "zero_wait": outcome.stats.commands_with_zero_wait,
            },
        }

        return {
            "plan_summary": plan.summary(),
            "dispatch": dispatch_summary,
            "actions": actions,
            "execution": execution_report,
            "metadata": plan.metadata,
            "status": "cq_actions_executed",
        }

    def _execute_cq_actions(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        executed: list[str] = []
        skipped: list[str] = []
        counts = {"dma": 0, "gemm": 0, "fence": 0}

        for action in actions:
            action_type = action.get("type")
            if action_type in counts:
                counts[action_type] += 1
            handler = {
                "dma": self._handle_cq_dma,
                "gemm": self._handle_cq_gemm,
                "fence": self._handle_cq_fence,
            }.get(action_type, self._handle_cq_unknown)
            if handler(action):
                executed.append(action["cmd_id"])
            else:
                skipped.append(action["cmd_id"])
            self.npu_cluster.schedule(self.bus.now)

        return {
            "executed": executed,
            "skipped": skipped,
            "count": counts,
            "estimate_cycles": sum(self._cq_gemm_cycle_log),
            "dma_bytes": self._cq_dma_bytes,
        }

    def _parse_cq_uri(self, uri: str) -> Tuple[str, str]:
        if not isinstance(uri, str) or "://" not in uri:
            raise ValueError(f"Invalid CQ URI: {uri}")
        scheme, path = uri.split("://", 1)
        return scheme, path

    def _ensure_cq_allocation(
        self, uri: str, size_bytes: int, *, shape: Optional[Tuple[int, ...]] = None
    ) -> Dict[str, Any]:
        space, key = self._parse_cq_uri(uri)
        if space == "dram":
            entry = self._cq_dram_allocations.get(key)
            new_entry = entry is None
            if new_entry:
                if (
                    self._cq_next_dram_addr + size_bytes
                    > DRAM_REGION.base + DRAM_REGION.size
                ):
                    raise MemoryError("CQ DRAM allocation exceeds region size")
                base = self._cq_next_dram_addr
                self._cq_next_dram_addr += size_bytes
                self.bus.write(base, bytes(size_bytes))
                entry = {"base": base, "size": size_bytes}
                self._cq_dram_allocations[key] = entry
            else:
                if size_bytes > entry["size"]:
                    raise MemoryError(
                        "CQ DRAM allocation for {uri} exceeds existing region "
                        "(requested {req}, allocated {alloc})".format(
                            uri=uri,
                            req=size_bytes,
                            alloc=entry["size"],
                        )
                    )
            if shape:
                entry["shape"] = shape
            self._initialize_cq_region(space, uri, entry, size_bytes, new_entry)
            return entry
        if space == "spm":
            entry = self._cq_spm_allocations.get(key)
            new_entry = entry is None
            if new_entry:
                if self._cq_next_spm_offset + size_bytes > SPM_REGION.size:
                    raise MemoryError("CQ SPM allocation exceeds region size")
                offset = self._cq_next_spm_offset
                self._cq_next_spm_offset += size_bytes
                entry = {"offset": offset, "size": size_bytes}
                self._cq_spm_allocations[key] = entry
            else:
                if size_bytes > entry["size"]:
                    raise MemoryError(
                        "CQ SPM allocation for {uri} exceeds existing region "
                        "(requested {req}, allocated {alloc})".format(
                            uri=uri,
                            req=size_bytes,
                            alloc=entry["size"],
                        )
                    )
            if shape:
                entry["shape"] = shape
            self._initialize_cq_region(space, uri, entry, size_bytes, new_entry)
            return entry
        raise ValueError(f"Unsupported CQ memory space: {space}")

    def _read_cq_tensor(self, uri: str, shape: Tuple[int, ...]) -> np.ndarray:
        size = int(np.prod(shape) * 4)
        space, key = self._parse_cq_uri(uri)
        entry = self._ensure_cq_allocation(uri, size, shape=shape)
        if space == "dram":
            base = entry["base"]
            data = self.bus.read(base, size)
        elif space == "spm":
            offset = entry["offset"]
            data = self.bus.read(SPM_REGION.base + offset, size)
        else:
            raise ValueError(f"Unsupported CQ memory space: {space}")
        array = np.frombuffer(data, dtype=np.float32)
        if array.size != int(np.prod(shape)):
            raise ValueError(
                f"CQ tensor size mismatch for {uri}: expected {shape}, got {array.size}"
            )
        return array.reshape(shape)

    def _initialize_cq_region(
        self,
        space: str,
        uri: str,
        entry: Dict[str, Any],
        size_bytes: int,
        new_entry: bool,
    ) -> None:
        init = self._cq_initial_data.get(uri)
        if init is None or not new_entry:
            return
        if init.dtype != np.float32:
            init = init.astype(np.float32)
        payload = init.tobytes()
        if len(payload) != size_bytes:
            message = (
                "Initial tensor size mismatch for {uri}: expected {expected}, "
                "got {actual}"
            ).format(uri=uri, expected=size_bytes, actual=len(payload))
            raise ValueError(message)
        entry["shape"] = tuple(int(dim) for dim in init.shape)
        self._write_bytes_to_space(space, entry, payload)
        entry["initialized"] = True

    def _write_bytes_to_space(
        self, space: str, entry: Dict[str, Any], payload: bytes
    ) -> None:
        if space == "dram":
            self.bus.write(entry["base"], payload)
            return
        if space == "spm":
            self.bus.write(SPM_REGION.base + entry["offset"], payload)
            return
        raise ValueError(f"Unsupported CQ memory space: {space}")

    def _write_cq_tensor(self, uri: str, data: np.ndarray) -> None:
        if data.dtype != np.float32:
            data = data.astype(np.float32)
        shape = tuple(int(dim) for dim in data.shape)
        buffer = data.tobytes()
        entry = self._ensure_cq_allocation(uri, len(buffer), shape=shape)
        space, _ = self._parse_cq_uri(uri)
        if space == "dram":
            self.bus.write(entry["base"], buffer)
        elif space == "spm":
            self.bus.write(SPM_REGION.base + entry["offset"], buffer)
        else:
            raise ValueError(f"Unsupported CQ memory space: {space}")

    def _handle_cq_dma(self, action: dict[str, Any]) -> bool:
        src = action.get("src")
        dst = action.get("dst")
        shape = tuple(int(dim) for dim in action.get("shape", ()))
        if not src or not dst or not shape:
            self.logger.warning("DMA action missing required fields: %s", action)
            return False
        bytes_len = int(np.prod(shape) * 4)
        self._ensure_cq_allocation(src, bytes_len, shape=shape)
        self._ensure_cq_allocation(dst, bytes_len, shape=shape)
        data = self._read_cq_tensor(src, shape)
        self._write_cq_tensor(dst, data)
        if bytes_len > 0:
            self._issue_bus_transfer(bytes_len)
            self._cq_dma_bytes += bytes_len
        self.logger.debug("CQ DMA executed: %s -> %s shape=%s", src, dst, shape)
        return True

    def _handle_cq_gemm(self, action: dict[str, Any]) -> bool:
        try:
            m = int(action["m"])
            n = int(action["n"])
            k = int(action["k"])
            inputs = action.get("inputs", {})
            a_uri = inputs.get("a")
            b_uri = inputs.get("b")
        except (KeyError, TypeError, ValueError):
            self.logger.warning("Invalid GEMM action: %s", action)
            return False

        if not a_uri or not b_uri:
            self.logger.warning("GEMM action missing tensor URIs: %s", action)
            return False

        a = self._read_cq_tensor(a_uri, (m, k))
        b = self._read_cq_tensor(b_uri, (k, n))
        result = a @ b
        out_uri = action.get("output") or a_uri
        self._write_cq_tensor(out_uri, result)
        compute_cycles = self._estimate_gemm_cycles(m, n, k)
        task = ClusterTask(
            input_bytes=0,
            output_bytes=0,
            compute_cycles=compute_cycles,
            issue_at=self.bus.now,
            name=action["cmd_id"],
        )
        submission = self.npu_cluster.submit(task)
        self.npu_cluster.schedule(self.bus.now)
        compute_done = submission.compute_done_at
        if compute_done <= 0:
            compute_done = self.bus.now + compute_cycles
            submission.compute_done_at = compute_done
        self.bus.sync_time(compute_done)
        self.npu_cluster.schedule(compute_done)
        final_done = submission.done_at if submission.done_at > 0 else compute_done
        self.bus.sync_time(final_done)
        self.npu_cluster.schedule(final_done)
        self._cq_gemm_cycle_log.append(compute_cycles)
        self.logger.debug("CQ GEMM executed: %s x %s -> %s", a_uri, b_uri, out_uri)
        return True

    def _handle_cq_fence(self, action: dict[str, Any]) -> bool:
        target = action.get("target")
        self.logger.debug("CQ FENCE noop: target=%s", target)
        return True

    def _handle_cq_unknown(self, action: dict[str, Any]) -> bool:
        self.logger.warning("CQ action type '%s' not recognised", action.get("type"))
        return False

    def _issue_bus_transfer(self, size_bytes: int) -> tuple[int, int]:
        if size_bytes <= 0:
            now = self.bus.now
            return now, now
        grant, done = self.bus.request(
            int(BusMasterID.NPU_DMA),
            size_bytes,
            request_at=self.bus.now,
        )
        self.bus.sync_time(done)
        return grant, done

    def _estimate_gemm_cycles(self, m: int, n: int, k: int) -> int:
        scale = self._get_config_section("npu").get("cores", 1) or 1
        cycles = max(1, int((m * n * k) / max(1, scale * 128)))
        return cycles

    def _get_config_section(self, *keys: str) -> Mapping[str, Any]:
        """Safely retrieve a nested mapping from the config tree."""

        section: Any = self._config
        for key in keys:
            if not isinstance(section, Mapping):
                return {}
            section = section.get(key, {})
        return section if isinstance(section, Mapping) else {}

    def _build_execution_config(self) -> ExecutionTimingConfig:
        defaults = ExecutionTimingConfig()
        exec_cfg = self._get_config_section("cpu", "execution")
        return ExecutionTimingConfig(
            alu_latency=self._coerce_int(
                exec_cfg.get("alu_latency"), defaults.alu_latency
            ),
            load_use_stall=self._coerce_int(
                exec_cfg.get("load_use_stall"), defaults.load_use_stall
            ),
            mul_latency=self._coerce_int(
                exec_cfg.get("mul_latency"), defaults.mul_latency
            ),
            div_latency=self._coerce_int(
                exec_cfg.get("div_latency"), defaults.div_latency
            ),
        )

    def _build_branch_config(self) -> BranchPredictorConfig:
        defaults = BranchPredictorConfig()
        branch_cfg = self._get_config_section("cpu", "branch")
        return BranchPredictorConfig(
            mispredict_penalty=self._coerce_int(
                branch_cfg.get("mispredict_penalty"), defaults.mispredict_penalty
            ),
            static_backwards_taken=bool(
                branch_cfg.get(
                    "static_backwards_taken", defaults.static_backwards_taken
                )
            ),
        )

    def _build_cache_config(
        self,
        name: str,
        data: Mapping[str, Any] | None,
        fallback: CacheConfig,
    ) -> CacheConfig:
        if not isinstance(data, Mapping):
            data = {}
        return CacheConfig(
            name=name,
            size_bytes=self._coerce_int(data.get("size_bytes"), fallback.size_bytes),
            line_size=self._coerce_int(data.get("line_size"), fallback.line_size),
            associativity=self._coerce_int(
                data.get("associativity"), fallback.associativity
            ),
            hit_latency=self._coerce_int(data.get("hit_latency"), fallback.hit_latency),
            write_back=bool(data.get("write_back", fallback.write_back)),
            write_allocate=bool(data.get("write_allocate", fallback.write_allocate)),
        )

    def _build_dram_config(self, data: Mapping[str, Any]) -> DRAMConfig:
        if not isinstance(data, Mapping):
            data = {}
        defaults = DRAMConfig()
        params = {
            "banks": self._coerce_int(data.get("banks"), defaults.banks),
            "row_size": self._coerce_int(data.get("row_size"), defaults.row_size),
            "line_size": self._coerce_int(data.get("line_size"), defaults.line_size),
            "t_rp": self._coerce_int(data.get("t_rp"), defaults.t_rp),
            "t_rcd": self._coerce_int(data.get("t_rcd"), defaults.t_rcd),
            "t_cas": self._coerce_int(data.get("t_cas"), defaults.t_cas),
            "data_bytes_per_cycle": self._coerce_int(
                data.get("data_bytes_per_cycle"), defaults.data_bytes_per_cycle
            ),
        }
        return DRAMConfig(**params)

    def _resolve_npu_policy(self) -> ClusterPolicy:
        npu_cfg = self._get_config_section("npu")
        policy_value = npu_cfg.get("policy")
        if not policy_value:
            return ClusterPolicy.MIN_FINISH_TIME
        try:
            return ClusterPolicy(policy_value)
        except ValueError:
            self.logger.warning(
                "Unknown NPU policy %s; falling back to MIN_FINISH_TIME", policy_value
            )
            return ClusterPolicy.MIN_FINISH_TIME

    def _resolve_npu_cores(self) -> int:
        npu_cfg = self._get_config_section("npu")
        cores_val = npu_cfg.get("cores", 2)
        try:
            cores = int(cores_val)
        except (ValueError, TypeError):
            self.logger.warning(
                "Invalid NPU cores value '%s'; falling back to 2.", cores_val
            )
            cores = 2
        return max(1, cores)

    def _build_determinism_config(self) -> DeterminismConfig:
        det_cfg = self._get_config_section("determinism")
        seed = self._coerce_int(det_cfg.get("seed"), 0)
        threads_raw = det_cfg.get("blas_threads", 1)
        try:
            threads = int(threads_raw)
        except (ValueError, TypeError):
            self.logger.warning(
                "Invalid BLAS thread count '%s'; falling back to 1.", threads_raw
            )
            threads = 1
        threads = max(1, threads)
        return DeterminismConfig(seed=seed, env_thread_value=str(threads))

    def _build_bus_config(self) -> Dict[str, int]:
        bus_cfg = self._get_config_section("bus")
        defaults = {
            "slice_bytes": 32,
            "bandwidth_bytes_per_cycle": 16,
            "grant_latency": 1,
        }
        return {
            key: self._coerce_int(bus_cfg.get(key), default)
            for key, default in defaults.items()
        }

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            if value is None:
                raise TypeError
            return int(value)
        except (ValueError, TypeError):
            return int(default)

    def load_program(
        self,
        program: Union[Iterable[int], ProgramImage],
        *,
        base_address: int = DRAM_REGION.base,
    ) -> None:
        image = self._materialize_program_image(program, base_address)

        self.risc_v_engine.pc = image.entry_point
        for segment in image.segments:
            if segment.mem_size == 0:
                continue

            if segment.data:
                self.bus.write(segment.address, segment.data)

            zero_padding = segment.mem_size - len(segment.data)
            if zero_padding <= 0:
                continue

            addr = segment.address + len(segment.data)
            remaining = zero_padding
            zero_chunk = bytearray(min(4096, remaining))
            while remaining > 0:
                chunk = min(remaining, len(zero_chunk))
                if chunk != len(zero_chunk):
                    zero_chunk = bytearray(chunk)
                self.bus.write(addr, zero_chunk)
                addr += chunk
                remaining -= chunk

    def _materialize_program_image(
        self, program: Union[Iterable[int], ProgramImage], base_address: int
    ) -> ProgramImage:
        if isinstance(program, ProgramImage):
            return program

        words = list(program)
        program_bytes = b"".join(
            int(word).to_bytes(4, "little", signed=False) for word in words
        )
        segment = ProgramSegment(
            address=base_address, data=program_bytes, mem_size=len(program_bytes)
        )
        return ProgramImage(
            instructions=words,
            text_size=len(program_bytes),
            entry_point=base_address,
            segments=[segment],
        )

    async def run_simulation(self, max_cycles: int = 0) -> SimulationReport:
        self.halt = False
        self.sim_time = 0
        self.risc_v_engine.instruction_count = 0
        cycles = 0
        reason = "completed"
        start_time = time.perf_counter()
        self._reset_fetch_stats()

        scheduler = EventScheduler()
        self.scheduler = scheduler

        def execute_instruction_event() -> None:
            nonlocal cycles, reason

            now = scheduler.now
            self.npu_cluster.schedule(now)
            self.sim_time = now
            self.bus.sync_time(self.sim_time)
            fetch_latency = 0
            self.risc_v_engine.begin_instruction(self.sim_time)

            if max_cycles > 0 and cycles >= max_cycles:
                reason = "max_cycles_reached"
                self.npu_cluster.schedule(self.bus.now)
                return

            fetch_start = self.risc_v_engine.current_time
            fetch_latency = self._issue_fetch(fetch_start)
            self.risc_v_engine.register_fetch_latency(fetch_latency, now=fetch_start)

            status = self.risc_v_engine.execute_instruction()
            cycles += 1

            if status == "halt":
                self.halt = True
                reason = "halt"
                self.npu_cluster.schedule(self.bus.now)
                return

            memory_delay = max(
                0, self.risc_v_engine.last_memory_done_at - scheduler.now
            )
            pipeline_delay = max(
                0, self.risc_v_engine.pipeline_ready_at - scheduler.now
            )
            next_delay = max(fetch_latency, memory_delay, pipeline_delay)
            if next_delay <= 0:
                next_delay = MIN_EVENT_DELAY
            scheduler.schedule_after(
                delay=next_delay, callback=execute_instruction_event
            )
            self.npu_cluster.schedule(self.bus.now)

        scheduler.schedule(timestamp=0, callback=execute_instruction_event)
        scheduler.run()

        final_time = max(self.bus.now, scheduler.now)
        self.npu_cluster.schedule(final_time)
        self.bus.sync_time(final_time)

        self.sim_time = scheduler.now
        elapsed = time.perf_counter() - start_time
        memory_report = self.memory_system.report_metrics()
        fetch_metrics = self._fetch_metrics()
        npu_metrics = self.npu_cluster.metrics(sim_time=self.sim_time)
        stall_breakdown = {
            "icache": fetch_metrics.get("miss_penalty_cycles", 0.0),
            "bus": memory_report.get("bus", {}).get("total_wait_cycles", 0.0),
            "dram": memory_report.get("memory_system", {}).get("dram_wait_cycles", 0.0),
            "npu_wait": npu_metrics.get("wait_cycles", 0.0),
        }
        return SimulationReport(
            cycles=cycles,
            instructions=self.risc_v_engine.instruction_count,
            halted=self.halt,
            reason=reason,
            sim_time=self.sim_time,
            elapsed_seconds=elapsed,
            memory_report=memory_report,
            stall_breakdown=stall_breakdown,
            npu_metrics=npu_metrics,
            fetch_metrics=fetch_metrics,
        )

    def _issue_fetch(self, start_time: int) -> int:
        done_at = self.memory_system.load(
            address=self.risc_v_engine.pc,
            size=WORD_SIZE_BYTES,
            request_time=start_time,
            master_id=BusMasterID.CPU,
        )
        latency = max(0, done_at - start_time)
        self._record_fetch_latency(latency)
        return latency

    def _record_fetch_latency(self, latency: int) -> None:
        self._fetch_stats["fetches"] += 1
        self._fetch_stats["total_latency"] += latency
        penalty = max(0, latency - self._fetch_hit_latency)
        if penalty > 0:
            self._fetch_stats["misses"] += 1
            self._fetch_stats["total_penalty"] += penalty

    def _reset_fetch_stats(self) -> None:
        self._fetch_stats = {
            "fetches": 0,
            "misses": 0,
            "total_latency": 0,
            "total_penalty": 0,
        }

    def _fetch_metrics(self) -> Dict[str, float | int]:
        fetches = self._fetch_stats["fetches"]
        misses = self._fetch_stats["misses"]
        total_latency = self._fetch_stats["total_latency"]
        total_penalty = self._fetch_stats["total_penalty"]
        miss_rate = (misses / fetches) if fetches else 0.0
        hit_rate = 1.0 - miss_rate
        average_latency = (total_latency / fetches) if fetches else 0.0
        return {
            "fetches": fetches,
            "misses": misses,
            "hit_rate": hit_rate,
            "miss_rate": miss_rate,
            "average_latency": average_latency,
            "miss_penalty_cycles": total_penalty,
        }


async def demo(max_cycles: int = 200_000) -> SimulationReport:
    """Run a minimal ADD program. Intended for manual experimentation."""

    simulator = AdaptiveSimulator()
    simulator.load_program([0x003100B3])
    return await simulator.run_simulation(max_cycles=max_cycles)


if __name__ == "__main__":  # pragma: no cover
    from src.simulator.cli import main as cli_main

    raise SystemExit(cli_main())
