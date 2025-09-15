import pytest
from src.simulator.main import AdaptiveSimulator

@pytest.mark.asyncio
async def test_end_to_end_add_instruction():
    """
    Tests the end-to-end simulation of a single ADD instruction.
    It checks if the instruction is fetched from memory, executed, and the result is written back to the register file.
    """
    # 1. Initialize the simulator
    simulator = AdaptiveSimulator()

    # 2. Load a simple program and initialize registers
    # ADD x1, x2, x3 (0x003100B3)
    simulator.load_program([0x003100B3])
    simulator.risc_v_engine.registers[2] = 10
    simulator.risc_v_engine.registers[3] = 20

    # 3. Run the simulation for one cycle
    await simulator.run_simulation(max_cycles=1)

    # 4. Verify the results
    # The result of 10 + 20 should be in register x1
    assert simulator.risc_v_engine.registers[1] == 30

    # The program counter should have advanced by 4
    assert simulator.risc_v_engine.pc == 4