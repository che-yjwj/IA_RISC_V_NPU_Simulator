from __future__ import annotations

import asyncio
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Union

# Ensure repository root is on sys.path when executed directly.
if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from src.risc_v.engine import RISCVEngine
from src.simulator.determinism import configure_deterministic_environment
from src.simulator.events import EventScheduler
from src.simulator.hooks import TimingHookSystem
from src.npu.cluster import ClusterPolicy, NPUCluster
from src.npu.model import NPU
from src.simulator.memory import MemorySystem, SPM, Bus
from src.simulator.mmio import MMIO
from src.simulator.program import ProgramImage, ProgramSegment

# Define memory map
DRAM_BASE = 0x00000000
DRAM_SIZE = 1024 * 1024  # 1MB
SPM_BASE = 0x10000000
SPM_SIZE_KB = 64
MMIO_BASE = 0x20000000
MMIO_SIZE = 0x10000  # 64KB


@dataclass(slots=True)
class SimulationReport:
    cycles: int
    instructions: int
    halted: bool
    reason: str
    sim_time: int
    elapsed_seconds: float
    bus_metrics: Dict[str, float | int]
    cache_metrics: Dict[str, Dict[str, float | int]]
    memory_metrics: Dict[str, float | int]
    stall_breakdown: Dict[str, float | int]
    npu_metrics: Dict[str, float | int]
    fetch_metrics: Dict[str, float | int]

    @property
    def mips(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return (self.instructions / 1_000_000) / self.elapsed_seconds


CPU_MASTER_ID = 0
NPU_DMA_MASTER_ID = 1
MIN_EVENT_DELAY = 1


class AdaptiveSimulator:
    """Primary integration point for CPU, NPU, and shared memory models."""

    def __init__(
        self,
        *,
        timing_hooks: Optional[TimingHookSystem] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        # Ensure deterministic seeding before any timing hooks or models allocate RNG state.
        configure_deterministic_environment()
        self.bus = Bus()
        self.dram = bytearray(DRAM_SIZE)
        self.spm = SPM(SPM_SIZE_KB)
        self.npu = NPU()
        self.npu_cluster = NPUCluster(
            self.bus,
            cores=2,
            dma_master_id=NPU_DMA_MASTER_ID,
            policy=ClusterPolicy.MIN_FINISH_TIME,
            compute_engine=self.npu,
        )
        self.mmio = MMIO(self.npu_cluster)
        self.memory_system = MemorySystem(self.bus)

        # Connect devices to the bus
        self.bus.add_device("dram", self.dram, DRAM_BASE, DRAM_BASE + DRAM_SIZE - 1)
        self.bus.add_device("spm", self.spm, SPM_BASE, SPM_BASE + (SPM_SIZE_KB * 1024) - 1)
        self.bus.add_device("mmio", self.mmio, MMIO_BASE, MMIO_BASE + MMIO_SIZE - 1)

        self.risc_v_engine = RISCVEngine(
            self.bus,
            self.memory_system,
            master_id=CPU_MASTER_ID,
        )
        self.timing_hooks = timing_hooks or TimingHookSystem()
        self.scheduler: Optional[EventScheduler] = None
        # self.event_system = EventBasedSystem() # This will be implemented later
        # self.fidelity_controller = FidelityController() # This will be implemented later
        self.halt = False
        self.sim_time = 0
        self.logger = logger or logging.getLogger(__name__)

    def load_program(
        self,
        program: Union[Iterable[int], ProgramImage],
        *,
        base_address: int = DRAM_BASE,
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
        program_bytes = b"".join(int(word).to_bytes(4, "little", signed=False) for word in words)
        segment = ProgramSegment(address=base_address, data=program_bytes, mem_size=len(program_bytes))
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

        scheduler = EventScheduler()
        self.scheduler = scheduler

        def execute_instruction_event() -> None:
            nonlocal cycles, reason

            self.sim_time = scheduler.now
            self.bus.sync_time(self.sim_time)
            self.risc_v_engine.begin_instruction(self.sim_time)

            if max_cycles > 0 and cycles >= max_cycles:
                reason = "max_cycles_reached"
                return

            status = self.risc_v_engine.execute_instruction()
            cycles += 1

            if status == "halt":
                self.halt = True
                reason = "halt"
                return

            latency = self.timing_hooks.fetch_hook(self.risc_v_engine.pc, 0)
            self.risc_v_engine.register_fetch_latency(latency, now=scheduler.now)
            memory_delay = max(0, self.risc_v_engine.last_memory_done_at - scheduler.now)
            pipeline_delay = max(0, self.risc_v_engine.pipeline_ready_at - scheduler.now)
            next_delay = max(latency, memory_delay, pipeline_delay)
            if next_delay <= 0:
                next_delay = MIN_EVENT_DELAY
            scheduler.schedule_after(delay=next_delay, callback=execute_instruction_event)

        scheduler.schedule(timestamp=0, callback=execute_instruction_event)
        scheduler.run()

        self.sim_time = scheduler.now
        elapsed = time.perf_counter() - start_time
        cache_metrics = self.memory_system.cache_metrics()
        memory_metrics = self.memory_system.memory_metrics()
        bus_metrics = self.bus.metrics.snapshot()
        fetch_metrics = self.timing_hooks.metrics() if hasattr(self.timing_hooks, "metrics") else {}
        npu_metrics = self.npu_cluster.metrics(sim_time=self.sim_time)
        stall_breakdown = {
            "icache": fetch_metrics.get("miss_penalty_cycles", 0.0),
            "bus": bus_metrics.get("total_wait_cycles", 0.0),
            "dram": memory_metrics.get("dram_wait_cycles", 0.0),
            "npu_wait": npu_metrics.get("wait_cycles", 0.0),
        }
        return SimulationReport(
            cycles=cycles,
            instructions=self.risc_v_engine.instruction_count,
            halted=self.halt,
            reason=reason,
            sim_time=self.sim_time,
            elapsed_seconds=elapsed,
            bus_metrics=bus_metrics,
            cache_metrics=cache_metrics,
            memory_metrics=memory_metrics,
            stall_breakdown=stall_breakdown,
            npu_metrics=npu_metrics,
            fetch_metrics=fetch_metrics,
        )


async def demo(max_cycles: int = 200_000) -> SimulationReport:
    """Run a minimal ADD program. Intended for manual experimentation."""

    simulator = AdaptiveSimulator()
    simulator.load_program([0x003100B3])
    return await simulator.run_simulation(max_cycles=max_cycles)


if __name__ == "__main__":  # pragma: no cover
    from src.simulator.cli import main as cli_main

    raise SystemExit(cli_main())
