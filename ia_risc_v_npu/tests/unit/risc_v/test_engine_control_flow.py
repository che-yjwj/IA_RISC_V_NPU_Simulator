
import pytest
import numpy as np
from src.risc_v.engine import (
    RISCVEngine,
    BranchPredictorConfig,
    ExecutionTimingConfig,
)
from src.simulator.memory import Bus, MemorySystem

OPCODE_R_TYPE = 0b0110011
OPCODE_I_TYPE_LOAD = 0b0000011

# Helper function to assemble B-type instructions
def assemble_b_type(funct3, rs1, rs2, imm):
    imm = imm & 0x1FFE # Ensure imm is 13 bits and 2-byte aligned

    # imm[12] is inst[31]
    # imm[11] is inst[7]
    # imm[10:5] is inst[30:25]
    # imm[4:1] is inst[11:8]

    return (((imm >> 12) & 0x1) << 31) | \
           (((imm >> 11) & 0x1) << 7)  | \
           (((imm >> 5) & 0x3F) << 25) | \
           (((imm >> 1) & 0xF) << 8)   | \
           (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | 0b1100011

# Helper function to assemble J-type instructions
def assemble_j_type(rd, imm):
    imm = imm & 0x1FFFFF  # Ensure imm is 21 bits
    imm20 = (imm >> 20) & 1
    imm19_12 = (imm >> 12) & 0xFF
    imm11 = (imm >> 11) & 1
    imm10_1 = (imm >> 1) & 0x3FF

    return (imm20 << 31) | (imm19_12 << 12) | (imm11 << 20) | (imm10_1 << 21) | (rd << 7) | 0b1101111


def assemble_r_type(rd, rs1, rs2, funct3, funct7):
    return (
        (funct7 << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | OPCODE_R_TYPE
    )


def assemble_i_type_load(rd, rs1, imm):
    encoded = imm & 0xFFF
    return (
        (encoded << 20)
        | (rs1 << 15)
        | (0b010 << 12)
        | (rd << 7)
        | OPCODE_I_TYPE_LOAD
    )


@pytest.fixture
def engine():
    bus = Bus()
    dram = bytearray(1024)
    bus.add_device("dram", dram, 0x0000, len(dram) - 1)
    memory_system = MemorySystem(bus)
    return RISCVEngine(
        bus,
        memory_system,
        branch_config=BranchPredictorConfig(mispredict_penalty=5),
        execution_timing=ExecutionTimingConfig(
            alu_latency=1,
            load_use_stall=1,
            mul_latency=4,
            div_latency=9,
        ),
    )

def test_jal_positive_offset(engine):
    instruction = 0x014000ef
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 20
    assert engine.registers[1] == 4

def test_jal_negative_offset(engine):
    # JAL x1, -20 (-0x14)
    instruction = assemble_j_type(1, -20)
    engine.bus.write(100, instruction.to_bytes(4, 'little'))
    engine.pc = 100
    
    engine.execute_instruction()
    
    assert engine.pc == 80  # 100 - 20
    assert engine.registers[1] == 104

def test_beq_taken(engine):
    # BEQ x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 10
    instruction = assemble_b_type(0b000, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0

    engine.execute_instruction()
    
    assert engine.pc == 40

def test_beq_not_taken(engine):
    # BEQ x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b000, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bne_taken(engine):
    # BNE x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b001, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bne_not_taken(engine):
    # BNE x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 10
    instruction = assemble_b_type(0b001, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_blt_taken_signed(engine):
    # BLT x1, x2, 40 (signed)
    engine.registers[1] = np.int32(-5)
    engine.registers[2] = np.int32(5)
    instruction = assemble_b_type(0b100, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0

    engine.execute_instruction()
    
    assert engine.pc == 40

def test_blt_not_taken_signed(engine):
    # BLT x1, x2, 40 (signed)
    engine.registers[1] = np.int32(10)
    engine.registers[2] = np.int32(-10)
    instruction = assemble_b_type(0b100, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bge_taken_signed(engine):
    # BGE x1, x2, 40 (signed)
    engine.registers[1] = np.int32(10)
    engine.registers[2] = np.int32(0)
    instruction = assemble_b_type(0b101, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bge_not_taken_signed(engine):
    # BGE x1, x2, 40 (signed)
    engine.registers[1] = np.int32(-10)
    engine.registers[2] = np.int32(10)
    instruction = assemble_b_type(0b101, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bltu_taken_unsigned(engine):
    # BLTU x1, x2, 40 (unsigned)
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b110, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bltu_not_taken_unsigned(engine):
    # BLTU x1, x2, 40 (unsigned)
    engine.registers[1] = 20
    engine.registers[2] = 10
    instruction = assemble_b_type(0b110, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bgeu_taken_unsigned(engine):
    # BGEU x1, x2, 40 (unsigned)
    engine.registers[1] = 20
    engine.registers[2] = 10
    instruction = assemble_b_type(0b111, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bgeu_not_taken_unsigned(engine):
    # BGEU x1, x2, 40 (unsigned)
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b111, 1, 2, 40)
    engine.bus.write(0, instruction.to_bytes(4, 'little'))
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4


def test_branch_backward_taken_no_mispredict(engine):
    # Backwards branch taken should be predicted taken → no penalty
    engine.registers[1] = 0
    engine.registers[2] = 0
    instruction = assemble_b_type(0b000, 1, 2, -8)
    addr = 16
    engine.bus.write(addr, instruction.to_bytes(4, "little"))
    engine.pc = addr

    engine.execute_instruction()

    assert engine.pc == addr - 8
    assert engine.pipeline_ready_at == engine.current_time


def test_branch_forward_taken_mispredict_applies_penalty(engine):
    # Forward branch that is taken should incur mispredict penalty
    engine.registers[1] = 0
    engine.registers[2] = 0
    instruction = assemble_b_type(0b000, 1, 2, 8)
    addr = 0
    engine.bus.write(addr, instruction.to_bytes(4, "little"))
    engine.pc = addr

    engine.execute_instruction()

    assert engine.pc == addr + 8
    expected_time = engine.exec_timing.alu_latency + engine.branch_config.mispredict_penalty
    assert engine.current_time == expected_time
    assert engine.pipeline_ready_at == engine.current_time


def test_load_use_dependency_introduces_stall(engine):
    data_value = 0xDEADBEEF
    data_addr = 128
    engine.bus.write(data_addr, data_value.to_bytes(4, "little"))

    load_inst = assemble_i_type_load(1, 0, data_addr)
    add_inst = assemble_r_type(2, 1, 0, 0b000, 0b0000000)

    engine.bus.write(0, load_inst.to_bytes(4, "little"))
    engine.bus.write(4, add_inst.to_bytes(4, "little"))
    engine.pc = 0

    engine.begin_instruction(0)
    engine.execute_instruction()

    load_ready = engine.register_ready_at[1]
    assert load_ready >= engine.last_memory_done_at

    next_time = engine.current_time
    engine.begin_instruction(next_time)
    engine.execute_instruction()

    assert engine.current_time >= load_ready
    assert engine.registers[2] == data_value & 0xFFFFFFFF
    assert engine.pipeline_ready_at >= engine.current_time


def test_mul_latency_respected(engine):
    mul_inst = assemble_r_type(5, 6, 7, 0b000, 0b0000001)
    engine.bus.write(0, mul_inst.to_bytes(4, "little"))
    engine.pc = 0
    engine.registers[6] = 3
    engine.registers[7] = 4

    engine.begin_instruction(0)
    engine.execute_instruction()

    assert engine.registers[5] == 12
    assert engine.current_time >= engine.exec_timing.mul_latency
    assert engine.pipeline_ready_at >= engine.current_time


def test_div_latency_respected(engine):
    div_inst = assemble_r_type(8, 9, 10, 0b100, 0b0000001)
    engine.bus.write(0, div_inst.to_bytes(4, "little"))
    engine.pc = 0
    engine.registers[9] = 18
    engine.registers[10] = 3

    engine.begin_instruction(0)
    engine.execute_instruction()

    assert engine.registers[8] == 6
    assert engine.current_time >= engine.exec_timing.div_latency
    assert engine.pipeline_ready_at >= engine.current_time


def test_div_signed_truncates_toward_zero(engine):
    div_inst = assemble_r_type(8, 9, 10, 0b100, 0b0000001)
    engine.bus.write(0, div_inst.to_bytes(4, "little"))
    engine.pc = 0
    engine.registers[9] = np.uint32(-7 & 0xFFFFFFFF)
    engine.registers[10] = np.uint32(3)

    engine.begin_instruction(0)
    engine.execute_instruction()

    assert np.int32(engine.registers[8]) == -2


def test_div_overflow_case_returns_min_int(engine):
    div_inst = assemble_r_type(8, 9, 10, 0b100, 0b0000001)
    engine.bus.write(0, div_inst.to_bytes(4, "little"))
    engine.pc = 0
    engine.registers[9] = np.uint32(0x80000000)
    engine.registers[10] = np.uint32(0xFFFFFFFF)

    engine.begin_instruction(0)
    engine.execute_instruction()

    assert engine.registers[8] == 0x80000000


def test_fetch_icache_latency_drives_frontend_stall(engine):
    add_inst = assemble_r_type(3, 1, 2, 0b000, 0b0000000)
    engine.bus.write(0, add_inst.to_bytes(4, "little"))
    engine.pc = 0
    engine.registers[1] = 1
    engine.registers[2] = 2

    engine.register_fetch_latency(4, now=0)
    engine.begin_instruction(0)
    engine.execute_instruction()

    assert engine.current_time >= 4
    assert engine.registers[3] == 3
