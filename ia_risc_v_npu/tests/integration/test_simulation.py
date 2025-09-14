import pytest
from src.risc_v.engine import RISCVEngine
from src.simulator.hooks import TimingHookSystem

def test_basic_simulation_loop():
    engine = RISCVEngine()
    hooks = TimingHookSystem()

    # This is a simplified simulation loop for testing purposes.
    # In the real simulator, this will be more complex.
    for _ in range(10):
        # Simulate fetching an instruction
        pc = 0 # dummy pc
        inst_bits = 0 # dummy instruction
        hooks.fetch_hook(pc, inst_bits)

        # Simulate executing an instruction
        engine.execute_instruction()

    # Check if the fetch hook was called
            # Check if the fetch hook was called
    assert hooks.counters['fetch'] == 10
