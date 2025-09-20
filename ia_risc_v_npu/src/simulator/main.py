from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from src.risc_v.engine import RISCVEngine
from src.simulator.hooks import TimingHookSystem
from src.npu.model import NPU
from src.simulator.memory import SPM, Bus
from src.simulator.mmio import MMIO

# Define memory map
DRAM_BASE = 0x00000000
DRAM_SIZE = 1024 * 1024  # 1MB
SPM_BASE = 0x10000000
SPM_SIZE_KB = 64
MMIO_BASE = 0x20000000
MMIO_SIZE = 0x10000  # 64KB

@dataclass(slots=True)
class SimulationResult:
    cycles: int
    halted: bool
    reason: str
    sim_time: int


class AdaptiveSimulator:
    """Primary integration point for CPU, NPU, and shared memory models."""

    def __init__(
        self,
        *,
        timing_hooks: Optional[TimingHookSystem] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.bus = Bus()
        self.dram = bytearray(DRAM_SIZE)
        self.spm = SPM(SPM_SIZE_KB)
        self.npu = NPU()
        self.mmio = MMIO(self.npu)

        # Connect devices to the bus
        self.bus.add_device("dram", self.dram, DRAM_BASE, DRAM_BASE + DRAM_SIZE - 1)
        self.bus.add_device("spm", self.spm, SPM_BASE, SPM_BASE + (SPM_SIZE_KB * 1024) - 1)
        self.bus.add_device("mmio", self.mmio, MMIO_BASE, MMIO_BASE + MMIO_SIZE - 1)

        self.risc_v_engine = RISCVEngine(self.bus)
        self.timing_hooks = timing_hooks or TimingHookSystem()
        # self.event_system = EventBasedSystem() # This will be implemented later
        # self.fidelity_controller = FidelityController() # This will be implemented later
        self.halt = False
        self.sim_time = 0
        self.logger = logger or logging.getLogger(__name__)

    def load_program(self, instructions: Iterable[int], *, base_address: int = DRAM_BASE) -> None:
        addr = base_address
        self.risc_v_engine.pc = base_address
        for inst in instructions:
            self.bus.write(addr, int(inst).to_bytes(4, "little", signed=False))
            addr += 4

    async def run_simulation(self, max_cycles: int = 0) -> SimulationResult:
        self.halt = False
        self.sim_time = 0
        self.risc_v_engine.instruction_count = 0
        cycles = 0
        reason = "completed"

        while not self.halt:
            if max_cycles > 0 and cycles >= max_cycles:
                reason = "max_cycles_reached"
                break
            status = self.risc_v_engine.execute_instruction()
            if status == "halt":
                self.halt = True
                reason = "halt"
                break
            latency = self.timing_hooks.fetch_hook(self.risc_v_engine.pc, 0)
            self.sim_time += latency
            cycles += 1

        return SimulationResult(
            cycles=cycles,
            halted=self.halt,
            reason=reason,
            sim_time=self.sim_time,
        )


async def demo(max_cycles: int = 200_000) -> SimulationResult:
    """Run a minimal ADD program. Intended for manual experimentation."""

    simulator = AdaptiveSimulator()
    simulator.load_program([0x003100B3])
    return await simulator.run_simulation(max_cycles=max_cycles)


if __name__ == "__main__":  # pragma: no cover
    from src.simulator.cli import main as cli_main

    raise SystemExit(cli_main())
