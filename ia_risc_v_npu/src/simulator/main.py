import asyncio
import sys
from pathlib import Path

# Ensure repository root is on sys.path when executed directly.
if __package__ is None:
    project_root = Path(__file__).resolve().parents[2]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

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

class AdaptiveSimulator:
    def __init__(self):
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
        self.timing_hooks = TimingHookSystem()
        # self.event_system = EventBasedSystem() # This will be implemented later
        # self.fidelity_controller = FidelityController() # This will be implemented later
        self.halt = False
        self.sim_time = 0

    def load_program(self, instructions: list[int]):
        addr = DRAM_BASE
        for inst in instructions:
            self.bus.write(addr, inst.to_bytes(4, 'little'))
            addr += 4

    async def run_simulation(self, max_cycles: int = 0):
        cycles = 0
        while not self.halt:
            if max_cycles > 0 and cycles >= max_cycles:
                break
            status = self.risc_v_engine.execute_instruction()
            if status == "halt":
                self.halt = True
                break
            # For now, we'll just use the timing hooks for latency
            latency = self.timing_hooks.fetch_hook(0, 0) # dummy values
            self.sim_time += latency
            cycles += 1
            await asyncio.sleep(0) # Yield control to the event loop

        # return SimulationResult(...) # This will be implemented later

async def main():
    simulator = AdaptiveSimulator()
    # Load a simple program: ADD x1, x2, x3
    simulator.load_program([0x003100B3])
    await simulator.run_simulation(max_cycles=200000)

if __name__ == "__main__":
    asyncio.run(main())
