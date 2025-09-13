def beq(state, rs1, rs2, imm):
    if rs1 == rs2:
        return state.pc + imm
    return state.pc + 4

def bne(state, rs1, rs2, imm):
    if rs1 != rs2:
        return state.pc + imm
    return state.pc + 4

def jal(state, imm):
    state.pc = state.pc + 4
    return state.pc + imm - 4 # The immediate is added to the original PC

def jalr(state, rs1, imm):
    state.pc = state.pc + 4
    return rs1 + imm