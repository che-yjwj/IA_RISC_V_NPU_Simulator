
import pytest
from src.risc_v.engine import RISCVEngine
from src.risc_v.instructions import alu, memory
from src.simulator.memory import Bus

# --- Instruction Constants ---
OPCODE_R_TYPE = 0b0110011
OPCODE_I_TYPE_LOAD = 0b0000011
OPCODE_S_TYPE_STORE = 0b0100011

# R-type funct3/funct7
FUNCT3_ADD_SUB = 0b000
FUNCT7_ADD = 0b0000000
FUNCT7_SUB = 0b0100000
FUNCT3_XOR = 0b100
FUNCT3_OR = 0b110
FUNCT3_AND = 0b111

# Other funct3
FUNCT3_LW = 0b010
FUNCT3_SW = 0b010

# Registers
RD_X1 = 1
RS1_X2 = 2
RS2_X3 = 3
RD_X4 = 4
RS1_X5 = 5
RS2_X6 = 6
RS1_X7 = 7

# Instructions
ADD_INSTRUCTION = (FUNCT7_ADD << 25) | (RS2_X3 << 20) | (RS1_X2 << 15) | (FUNCT3_ADD_SUB << 12) | (RD_X1 << 7) | OPCODE_R_TYPE
SUB_INSTRUCTION = (FUNCT7_SUB << 25) | (RS2_X3 << 20) | (RS1_X2 << 15) | (FUNCT3_ADD_SUB << 12) | (RD_X1 << 7) | OPCODE_R_TYPE
XOR_INSTRUCTION = (FUNCT7_ADD << 25) | (RS2_X3 << 20) | (RS1_X2 << 15) | (FUNCT3_XOR << 12) | (RD_X1 << 7) | OPCODE_R_TYPE
OR_INSTRUCTION = (FUNCT7_ADD << 25) | (RS2_X3 << 20) | (RS1_X2 << 15) | (FUNCT3_OR << 12) | (RD_X1 << 7) | OPCODE_R_TYPE
AND_INSTRUCTION = (FUNCT7_ADD << 25) | (RS2_X3 << 20) | (RS1_X2 << 15) | (FUNCT3_AND << 12) | (RD_X1 << 7) | OPCODE_R_TYPE

IMM_LW = 8
LW_INSTRUCTION = (IMM_LW << 20) | (RS1_X5 << 15) | (FUNCT3_LW << 12) | (RD_X4 << 7) | OPCODE_I_TYPE_LOAD

IMM_SW = 12
IMM1_SW = IMM_SW & 0x1F
IMM2_SW = (IMM_SW >> 5) & 0x7F
SW_INSTRUCTION = (IMM2_SW << 25) | (RS2_X6 << 20) | (RS1_X7 << 15) | (FUNCT3_SW << 12) | (IMM1_SW << 7) | OPCODE_S_TYPE_STORE


class ReferenceRISCVEngine:
    def __init__(self, registers, bus):
        self.registers = registers
        self.bus = bus
        self.pc = 0

    def _execute_r_type(self, operation, rd, rs1, rs2):
        if rd != 0:
            self.registers[rd] = operation(self.registers[rs1], self.registers[rs2]) & 0xFFFFFFFF
        self.pc += 4

    def execute_add(self, rd, rs1, rs2): self._execute_r_type(alu.add, rd, rs1, rs2)
    def execute_sub(self, rd, rs1, rs2): self._execute_r_type(alu.sub, rd, rs1, rs2)
    def execute_xor(self, rd, rs1, rs2): self._execute_r_type(alu.xor, rd, rs1, rs2)
    def execute_or(self, rd, rs1, rs2): self._execute_r_type(alu.or_, rd, rs1, rs2)
    def execute_and(self, rd, rs1, rs2): self._execute_r_type(alu.and_, rd, rs1, rs2)

    def execute_lw(self, rd, rs1, imm):
        if rd != 0:
            address = self.registers[rs1] + imm
            self.registers[rd] = memory.lw(self.bus, address)
        self.pc += 4

    def execute_sw(self, rs1, rs2, imm):
        address = self.registers[rs1] + imm
        memory.sw(self.bus, address, self.registers[rs2])
        self.pc += 4


class TestInstructionAccuracy:
    def setup_method(self):
        self.bus = Bus()
        self.dram = bytearray(1024)
        self.bus.add_device("dram", self.dram, 0x0000, 0x03FF)

        self.initial_registers = [0] * 32
        self.initial_registers[RS1_X2] = 0x8000000A # 10 with MSB set
        self.initial_registers[RS2_X3] = 20
        self.initial_registers[RS1_X5] = 100
        self.initial_registers[RS2_X6] = 0xDEADBEEF
        self.initial_registers[RS1_X7] = 200

        self.main_engine = RISCVEngine(self.bus)
        self.ref_engine = ReferenceRISCVEngine([0]*32, self.bus)
        self.reset_states()

    def reset_states(self):
        self.main_engine.registers = self.initial_registers[:]
        self.main_engine.pc = 0
        self.ref_engine.registers = self.initial_registers[:]
        self.ref_engine.pc = 0
        self.dram.fromhex('00' * 1024)

    def compare_states(self):
        assert self.main_engine.pc == self.ref_engine.pc
        assert self.main_engine.registers == self.ref_engine.registers

    def _run_single_instruction_test(self, test_name, instruction_bytes, ref_executor, *args):
        self.reset_states()
        self.bus.write(0, instruction_bytes)
        self.main_engine.execute_instruction()
        ref_executor(*args)
        self.compare_states()

    def test_add_instruction(self):
        self._run_single_instruction_test("ADD", ADD_INSTRUCTION.to_bytes(4, 'little'), self.ref_engine.execute_add, RD_X1, RS1_X2, RS2_X3)
        assert self.main_engine.registers[RD_X1] == (self.initial_registers[RS1_X2] + self.initial_registers[RS2_X3]) & 0xFFFFFFFF

    def test_sub_instruction(self):
        self._run_single_instruction_test("SUB", SUB_INSTRUCTION.to_bytes(4, 'little'), self.ref_engine.execute_sub, RD_X1, RS1_X2, RS2_X3)
        assert self.main_engine.registers[RD_X1] == (self.initial_registers[RS1_X2] - self.initial_registers[RS2_X3]) & 0xFFFFFFFF

    def test_xor_instruction(self):
        self._run_single_instruction_test("XOR", XOR_INSTRUCTION.to_bytes(4, 'little'), self.ref_engine.execute_xor, RD_X1, RS1_X2, RS2_X3)
        assert self.main_engine.registers[RD_X1] == (self.initial_registers[RS1_X2] ^ self.initial_registers[RS2_X3]) & 0xFFFFFFFF

    def test_or_instruction(self):
        self._run_single_instruction_test("OR", OR_INSTRUCTION.to_bytes(4, 'little'), self.ref_engine.execute_or, RD_X1, RS1_X2, RS2_X3)
        assert self.main_engine.registers[RD_X1] == (self.initial_registers[RS1_X2] | self.initial_registers[RS2_X3]) & 0xFFFFFFFF

    def test_and_instruction(self):
        self._run_single_instruction_test("AND", AND_INSTRUCTION.to_bytes(4, 'little'), self.ref_engine.execute_and, RD_X1, RS1_X2, RS2_X3)
        assert self.main_engine.registers[RD_X1] == (self.initial_registers[RS1_X2] & self.initial_registers[RS2_X3]) & 0xFFFFFFFF

    def test_lw_instruction(self):
        self.reset_states()
        memory_address = self.initial_registers[RS1_X5] + IMM_LW
        value_to_load = 0xABCDEF01
        self.bus.write(memory_address, value_to_load.to_bytes(4, 'little'))
        self._run_single_instruction_test("LW", LW_INSTRUCTION.to_bytes(4, 'little'), self.ref_engine.execute_lw, RD_X4, RS1_X5, IMM_LW)
        assert self.main_engine.registers[RD_X4] == value_to_load

    def test_sw_instruction(self):
        self.reset_states()
        self._run_single_instruction_test("SW", SW_INSTRUCTION.to_bytes(4, 'little'), self.ref_engine.execute_sw, RS1_X7, RS2_X6, IMM_SW)
        memory_address = self.initial_registers[RS1_X7] + IMM_SW
        stored_value = int.from_bytes(self.bus.read(memory_address, 4), 'little')
        assert stored_value == self.initial_registers[RS2_X6]
