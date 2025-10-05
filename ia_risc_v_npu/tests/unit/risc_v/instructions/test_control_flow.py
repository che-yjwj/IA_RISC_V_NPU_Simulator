from src.risc_v.instructions.control_flow import (
    beq,
    bge,
    bgeu,
    blt,
    bltu,
    bne,
    jal,
    jalr,
)


# This is a simplified representation of the processor state for testing purposes.
class ProcessorState:
    def __init__(self, pc=0):
        self.pc = pc


def test_beq():
    # Branch if equal
    assert beq(10, 10)
    # Don't branch if not equal
    assert not beq(10, 20)


def test_bne():
    # Branch if not equal
    assert bne(10, 20)
    # Don't branch if equal
    assert not bne(10, 10)


def test_blt():
    # Signed less than
    assert blt(10, 20)
    assert blt(-10, 20)
    assert blt(-20, -10)
    assert not blt(20, 10)
    assert not blt(10, 10)


def test_bge():
    # Signed greater than or equal
    assert bge(20, 10)
    assert bge(10, 10)
    assert bge(-10, -20)
    assert not bge(10, 20)


def test_bltu():
    # Unsigned less than
    assert bltu(10, 20)
    assert bltu(0, 1)
    assert not bltu(20, 10)
    assert not bltu(10, 10)
    # Unsigned comparison with negative numbers
    assert not bltu(0xFFFFFFFF, 0)  # -1 is not less than 0 unsigned


def test_bgeu():
    # Unsigned greater than or equal
    assert bgeu(20, 10)
    assert bgeu(10, 10)
    assert bgeu(1, 0)
    assert not bgeu(10, 20)
    # Unsigned comparison with negative numbers
    assert bgeu(0xFFFFFFFF, 0)  # -1 is greater than 0 unsigned


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
