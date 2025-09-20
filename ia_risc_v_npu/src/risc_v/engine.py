import logging

from src.risc_v.instructions import alu, memory, control_flow
import numpy as np

# Instruction format constants
OPCODE_R_TYPE = 0b0110011
OPCODE_I_TYPE_LOAD = 0b0000011
OPCODE_S_TYPE_STORE = 0b0100011
OPCODE_B_TYPE = 0b1100011
OPCODE_R4_TYPE_FMADD = 0b1000011
OPCODE_J_TYPE_JAL = 0b1101111

# Funct3 constants for R-type
FUNCT3_ADD_SUB = 0b000
FUNCT3_XOR = 0b100
FUNCT3_OR = 0b110
FUNCT3_AND = 0b111

# Funct7 constants for R-type
FUNCT7_ADD = 0b0000000
FUNCT7_SUB = 0b0100000

# Funct3 constants for other types
FUNCT3_LW = 0b010
FUNCT3_SW = 0b010
FUNCT3_FMADD = 0b000

LOGGER = logging.getLogger(__name__)


class RISCVEngine:
    def __init__(self, bus):
        self.pc = 0
        self.registers = np.zeros(32, dtype=np.uint32)
        self.bus = bus
        self.instruction_count = 0

        # Initialize registers for testing
        self.registers[2] = 10
        self.registers[3] = 20

    def _read_word(self, address):
        return int.from_bytes(self.bus.read(address, 4), 'little')

    def _decode_r_type_instruction(self, instruction):
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        funct7 = (instruction >> 25) & 0x7F
        return opcode, rd, funct3, rs1, rs2, funct7

    def _decode_i_type_instruction(self, instruction):
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        imm = (instruction >> 20) & 0xFFF
        if (imm >> 11) & 1:
            imm -= 1 << 12
        return opcode, rd, funct3, rs1, imm

    def _decode_s_type_instruction(self, instruction):
        opcode = instruction & 0x7F
        imm1 = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        imm2 = (instruction >> 25) & 0x7F
        imm = (imm2 << 5) | imm1
        if (imm >> 11) & 1:
            imm -= 1 << 12
        return opcode, funct3, rs1, rs2, imm

    def _decode_r4_type_instruction(self, instruction):
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        rs3 = (instruction >> 27) & 0x1F
        return opcode, rd, funct3, rs1, rs2, rs3

    def _decode_j_type_instruction(self, instruction: int) -> tuple[int, int, int]:
        imm_20 = (instruction >> 31) & 0x1
        imm_10_1 = (instruction >> 21) & 0x3FF
        imm_11 = (instruction >> 20) & 0x1
        imm_19_12 = (instruction >> 12) & 0xFF

        imm = (imm_20 << 20) | (imm_19_12 << 12) | (imm_11 << 11) | (imm_10_1 << 1)

        # Sign-extend the 21-bit immediate to 32 bits
        if imm & (1 << 20):
            imm -= (1 << 21)

        rd = (instruction >> 7) & 0x1F
        opcode = instruction & 0x7F

        return opcode, rd, imm

    def _decode_b_type_instruction(self, instruction):
        opcode = instruction & 0x7F
        imm1 = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        imm2 = (instruction >> 25) & 0x7F
        imm = ((instruction >> 31) & 0x1) << 12 | \
              ((instruction >> 7) & 0x1) << 11  | \
              ((instruction >> 25) & 0x3F) << 5 | \
              ((instruction >> 8) & 0xF) << 1
        
        # Sign-extend the 13-bit immediate to 32 bits
        if imm & (1 << 12):
            imm -= (1 << 13)
        return opcode, funct3, rs1, rs2, imm

    def _execute_alu_instruction(self, funct3, rd, rs1, rs2, funct7):
        if rd == 0: # x0 is hardwired to zero, so no-op
            return

        result = 0
        if funct3 == FUNCT3_ADD_SUB:
            if funct7 == FUNCT7_ADD:
                result = alu.add(self.registers[rs1], self.registers[rs2])
            elif funct7 == FUNCT7_SUB:
                result = alu.sub(self.registers[rs1], self.registers[rs2])
            else:
                raise ValueError(f"Unsupported ALU instruction for funct3={funct3}: funct7={funct7}")
        elif funct3 == FUNCT3_XOR:
            result = alu.xor(self.registers[rs1], self.registers[rs2])
        elif funct3 == FUNCT3_OR:
            result = alu.or_(self.registers[rs1], self.registers[rs2])
        elif funct3 == FUNCT3_AND:
            result = alu.and_(self.registers[rs1], self.registers[rs2])
        else:
            raise ValueError(f"Unsupported ALU instruction: funct3={funct3}")
        
        self.registers[rd] = result & 0xFFFFFFFF

    def _execute_load_instruction(self, funct3, rd, rs1, imm):
        if funct3 == FUNCT3_LW:
            address = self.registers[rs1] + imm
            if rd != 0:
                self.registers[rd] = memory.lw(self.bus, address)
        else:
            raise ValueError(f"Unsupported load instruction: funct3={funct3}")

    def _execute_store_instruction(self, funct3, rs1, rs2, imm):
        if funct3 == FUNCT3_SW:
            address = self.registers[rs1] + imm
            memory.sw(self.bus, address, self.registers[rs2])
        else:
            raise ValueError(f"Unsupported store instruction: funct3={funct3}")

    def _execute_fmadd_instruction(self, funct3, rd, rs1, rs2, rs3):
        if funct3 == FUNCT3_FMADD:
            if rd != 0:
                result = alu.fmadd(self.registers[rs1], self.registers[rs2], self.registers[rs3])
                self.registers[rd] = result & 0xFFFFFFFF
        else:
            raise ValueError(f"Unsupported FMADD instruction: funct3={funct3}")

    def _execute_jal_instruction(self, rd, imm, original_pc):
        if rd != 0:
            self.registers[rd] = original_pc + 4
        self.pc = original_pc + imm

    def _execute_branch_instruction(self, funct3, rs1, rs2, imm, original_pc):
        val1 = self.registers[rs1]
        val2 = self.registers[rs2]
        
        branch_taken = False
        if funct3 == 0b000: # BEQ
            branch_taken = control_flow.beq(val1, val2)
        elif funct3 == 0b001: # BNE
            branch_taken = control_flow.bne(val1, val2)
        elif funct3 == 0b100: # BLT
            branch_taken = control_flow.blt(val1, val2)
        elif funct3 == 0b101: # BGE
            branch_taken = control_flow.bge(val1, val2)
        elif funct3 == 0b110: # BLTU
            branch_taken = control_flow.bltu(val1, val2)
        elif funct3 == 0b111: # BGEU
            branch_taken = control_flow.bgeu(val1, val2)

        if branch_taken:
            self.pc = original_pc + imm
            LOGGER.debug("branch taken: 0x%08x -> 0x%08x", original_pc, self.pc)

    def execute_instruction(self):
        self.instruction_count += 1
        instruction = self._read_word(self.pc)
        LOGGER.debug("pc=0x%08x instruction=0x%08x", self.pc, instruction)
        original_pc = self.pc
        opcode = instruction & 0x7F

        if instruction == 0:
            return "halt"

        pc_changed = False
        if opcode == OPCODE_R_TYPE:
            _, rd, funct3, rs1, rs2, funct7 = self._decode_r_type_instruction(instruction)
            self._execute_alu_instruction(funct3, rd, rs1, rs2, funct7)
        elif opcode == OPCODE_I_TYPE_LOAD:
            _, rd, funct3, rs1, imm = self._decode_i_type_instruction(instruction)
            self._execute_load_instruction(funct3, rd, rs1, imm)
        elif opcode == OPCODE_S_TYPE_STORE:
            _, funct3, rs1, rs2, imm = self._decode_s_type_instruction(instruction)
            self._execute_store_instruction(funct3, rs1, rs2, imm)
        elif opcode == OPCODE_B_TYPE:
            _, funct3, rs1, rs2, imm = self._decode_b_type_instruction(instruction)
            self._execute_branch_instruction(funct3, rs1, rs2, imm, original_pc)
            if self.pc != original_pc: # if branch was taken
                pc_changed = True
        elif opcode == OPCODE_R4_TYPE_FMADD:
            _, rd, funct3, rs1, rs2, rs3 = self._decode_r4_type_instruction(instruction)
            self._execute_fmadd_instruction(funct3, rd, rs1, rs2, rs3)
        elif opcode == OPCODE_J_TYPE_JAL:
            _, rd, imm = self._decode_j_type_instruction(instruction)
            if rd == 0 and imm == 0:
                return "halt"
            self._execute_jal_instruction(rd, imm, original_pc)
            LOGGER.debug("jump: 0x%08x -> 0x%08x", original_pc, self.pc)
            pc_changed = True
        else:
            raise ValueError(f"Unsupported opcode: {opcode}")
        
        if not pc_changed:
            self.pc += 4
        
        return "continue"
