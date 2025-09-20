
import pytest
import numpy as np
from src.risc_v.engine import RISCVEngine
from src.simulator.memory import Memory

# Helper function to assemble B-type instructions
def assemble_b_type(funct3, rs1, rs2, imm):
    imm = imm & 0x1FFF  # Ensure imm is 13 bits
    imm12 = (imm >> 12) & 1
    imm11 = (imm >> 11) & 1
    imm10_5 = (imm >> 5) & 0x3F
    imm4_1 = (imm >> 1) & 0xF
    
    imm_field1 = (imm10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm4_1 << 8) | (imm11 << 7) | 0b1100011
    imm_field2 = (imm12 << 31)
    return imm_field2 | imm_field1

# Helper function to assemble J-type instructions
def assemble_j_type(rd, imm):
    imm = imm & 0x1FFFFF  # Ensure imm is 21 bits
    imm20 = (imm >> 20) & 1
    imm19_12 = (imm >> 12) & 0xFF
    imm11 = (imm >> 11) & 1
    imm10_1 = (imm >> 1) & 0x3FF

    return (imm20 << 31) | (imm19_12 << 12) | (imm11 << 20) | (imm10_1 << 21) | (rd << 7) | 0b1101111


@pytest.fixture
def engine():
    bus = Memory(size=1024 * 1024)  # 1MB memory
    return RISCVEngine(bus)

def test_jal_positive_offset(engine):
    # JAL x1, 20 (0x14)
    # 0x014000ef = jal x1, 20
    instruction = 0x014000ef
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 20
    assert engine.registers[1] == 4

def test_jal_negative_offset(engine):
    # JAL x1, -20 (-0x14)
    instruction = assemble_j_type(1, -20)
    engine.bus.write_word(100, instruction)
    engine.pc = 100
    
    engine.execute_instruction()
    
    assert engine.pc == 80  # 100 - 20
    assert engine.registers[1] == 104

def test_beq_taken(engine):
    # BEQ x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 10
    instruction = assemble_b_type(0b000, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_beq_not_taken(engine):
    # BEQ x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b000, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bne_taken(engine):
    # BNE x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b001, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bne_not_taken(engine):
    # BNE x1, x2, 40
    engine.registers[1] = 10
    engine.registers[2] = 10
    instruction = assemble_b_type(0b001, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_blt_taken_signed(engine):
    # BLT x1, x2, 40 (signed)
    engine.registers[1] = np.int32(-10)
    engine.registers[2] = np.int32(10)
    instruction = assemble_b_type(0b100, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_blt_not_taken_signed(engine):
    # BLT x1, x2, 40 (signed)
    engine.registers[1] = np.int32(10)
    engine.registers[2] = np.int32(-10)
    instruction = assemble_b_type(0b100, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bge_taken_signed(engine):
    # BGE x1, x2, 40 (signed)
    engine.registers[1] = np.int32(10)
    engine.registers[2] = np.int32(-10)
    instruction = assemble_b_type(0b101, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bge_not_taken_signed(engine):
    # BGE x1, x2, 40 (signed)
    engine.registers[1] = np.int32(-10)
    engine.registers[2] = np.int32(10)
    instruction = assemble_b_type(0b101, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bltu_taken_unsigned(engine):
    # BLTU x1, x2, 40 (unsigned)
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b110, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bltu_not_taken_unsigned(engine):
    # BLTU x1, x2, 40 (unsigned)
    engine.registers[1] = 20
    engine.registers[2] = 10
    instruction = assemble_b_type(0b110, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4

def test_bgeu_taken_unsigned(engine):
    # BGEU x1, x2, 40 (unsigned)
    engine.registers[1] = 20
    engine.registers[2] = 10
    instruction = assemble_b_type(0b111, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 40

def test_bgeu_not_taken_unsigned(engine):
    # BGEU x1, x2, 40 (unsigned)
    engine.registers[1] = 10
    engine.registers[2] = 20
    instruction = assemble_b_type(0b111, 1, 2, 40)
    engine.bus.write_word(0, instruction)
    engine.pc = 0
    
    engine.execute_instruction()
    
    assert engine.pc == 4
