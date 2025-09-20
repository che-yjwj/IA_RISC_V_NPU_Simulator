import asyncio

from src.simulator.main import AdaptiveSimulator


def test_end_to_end_add_instruction():
    """
    Tests the end-to-end simulation of a single ADD instruction.
    It checks if the instruction is fetched from memory, executed, and the result is written back to the register file.
    """
    async def scenario():
        simulator = AdaptiveSimulator()

        # ADD x1, x2, x3 (0x003100B3)
        simulator.load_program([0x003100B3])
        simulator.risc_v_engine.registers[2] = 10
        simulator.risc_v_engine.registers[3] = 20

        report = await simulator.run_simulation(max_cycles=1)

        assert simulator.risc_v_engine.registers[1] == 30
        assert simulator.risc_v_engine.pc == 4
        assert report.instructions == 1
        assert report.elapsed_seconds >= 0

    asyncio.run(scenario())
