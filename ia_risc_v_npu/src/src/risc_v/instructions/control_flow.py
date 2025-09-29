import numpy as np

def beq(rs1, rs2):
    """Branch if equal."""
    return rs1 == rs2

def bne(rs1, rs2):
    """Branch if not equal."""
    return rs1 != rs2

def blt(rs1, rs2):
    """Branch if less than (signed)."""
    return np.int32(rs1) < np.int32(rs2)

def bge(rs1, rs2):
    """Branch if greater than or equal (signed)."""
    return np.int32(rs1) >= np.int32(rs2)

def bltu(rs1, rs2):
    """Branch if less than (unsigned)."""
    return rs1 < rs2

def bgeu(rs1, rs2):
    """Branch if greater than or equal (unsigned)."""
    return rs1 >= rs2

def jal(state, imm):
    state.pc = state.pc + 4
    return state.pc + imm - 4 # The immediate is added to the original PC

def jalr(state, rs1, imm):
    state.pc = state.pc + 4
    return rs1 + imm