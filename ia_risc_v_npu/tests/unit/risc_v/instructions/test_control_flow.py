import pytest
from src.risc_v.instructions.control_flow import beq, bne, jal, jalr

# This is a simplified representation of the processor state for testing purposes.
class ProcessorState:
    def __init__(self, pc=0):
        self.pc = pc

def test_beq():
    state = ProcessorState()
    # Branch if equal
    assert beq(state, 10, 10, 20) == 20
    # Don't branch if not equal
    assert beq(state, 10, 20, 20) == 4

def test_bne():
    state = ProcessorState()
    # Branch if not equal
    assert bne(state, 10, 20, 20) == 20
    # Don't branch if equal
    assert bne(state, 10, 10, 20) == 4

def test_jal():
    state = ProcessorState()
    # Jump and link
    assert jal(state, 20) == 20
    assert state.pc == 4

def test_jalr():
    state = ProcessorState()
    # Jump and link register
    assert jalr(state, 10, 20) == 30
    assert state.pc == 4
