import pytest
from src.simulator.adaptive_controller import FidelityController

# This is a simplified representation of an instruction result for testing purposes.
class InstructionResult:
    def __init__(self, complexity):
        self.complexity = complexity

def test_fidelity_controller():
    controller = FidelityController()

    # Low complexity instruction should use Lev0
    low_complexity_inst = InstructionResult(complexity=0.2)
    assert controller.should_use_lev1(low_complexity_inst) == False

    # High complexity instruction should use Lev1
    high_complexity_inst = InstructionResult(complexity=0.8)
    assert controller.should_use_lev1(high_complexity_inst) == True
