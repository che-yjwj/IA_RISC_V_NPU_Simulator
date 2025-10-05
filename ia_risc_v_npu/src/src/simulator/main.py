from __future__ import annotations

import logging
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Union

# Ensure repository root is on sys.path when executed directly.
if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from src.npu.cluster import ClusterPolicy, NPUCluster
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
from src.simulator.devices import (
    SPM,
    Bus,
)
from src.simulator.models import (
    CacheConfig,
    DRAMConfig,
)
from src.simulator.memory import (
    MemorySystem,
)
from src.simulator.mmio import MMIO
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
