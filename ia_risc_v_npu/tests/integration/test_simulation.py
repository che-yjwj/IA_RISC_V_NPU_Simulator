import pytest
from src.simulator.main import AdaptiveSimulator

@pytest.mark.asyncio
async def test_end_to_end_add_instruction():
    """
    Tests the end-to-end simulation of a single ADD instruction.
    It checks if the instruction is fetched from memory, executed, and the result is written back to the register file.
    """
    # 1. Initialize the simulator
    simulator = AdaptiveSimulator(config_path="")

    # 2. The simulator by default loads an ADD instruction (add x1, x2, x3)
    # and sets x2=10, x3=20.

    # 3. Run the simulation for one cycle
    await simulator.run_simulation(max_cycles=1)

    # 4. Verify the results
    # The result of 10 + 20 should be in register x1
    assert simulator.risc_v_engine.registers[1] == 30

    # The program counter should have advanced by 4
    assert simulator.risc_v_engine.pc == 4