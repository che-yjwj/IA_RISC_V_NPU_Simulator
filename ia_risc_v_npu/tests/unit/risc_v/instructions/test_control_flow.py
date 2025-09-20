import pytest
from src.risc_v.instructions.control_flow import beq, bne, blt, bge, bltu, bgeu, jal, jalr

# This is a simplified representation of the processor state for testing purposes.
class ProcessorState:
    def __init__(self, pc=0):
        self.pc = pc

def test_beq():
    # Branch if equal
    assert beq(10, 10) == True
    # Don't branch if not equal
    assert beq(10, 20) == False

def test_bne():
    # Branch if not equal
    assert bne(10, 20) == True
    # Don't branch if equal
    assert bne(10, 10) == False

def test_blt():
    # Signed less than
    assert blt(10, 20) == True
    assert blt(-10, 20) == True
    assert blt(-20, -10) == True
    assert blt(20, 10) == False
    assert blt(10, 10) == False

def test_bge():
    # Signed greater than or equal
    assert bge(20, 10) == True
    assert bge(10, 10) == True
    assert bge(-10, -20) == True
    assert bge(10, 20) == False

def test_bltu():
    # Unsigned less than
    assert bltu(10, 20) == True
    assert bltu(0, 1) == True
    assert bltu(20, 10) == False
    assert bltu(10, 10) == False
    # Unsigned comparison with negative numbers
    assert bltu(0xFFFFFFFF, 0) == False # -1 is not less than 0 unsigned

def test_bgeu():
    # Unsigned greater than or equal
    assert bgeu(20, 10) == True
    assert bgeu(10, 10) == True
    assert bgeu(1, 0) == True
    assert bgeu(10, 20) == False
    # Unsigned comparison with negative numbers
    assert bgeu(0xFFFFFFFF, 0) == True # -1 is greater than 0 unsigned

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
