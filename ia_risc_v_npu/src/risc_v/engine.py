from src.risc_v.instructions import alu

# Instruction format constants
OPCODE_R_TYPE = 0b0110011
FUNCT3_ADD = 0b000
FUNCT7_ADD = 0b0000000

class RISCVEngine:
    def __init__(self):
        self.pc = 0
        self.registers = [0] * 32
        self.memory = bytearray(1024 * 1024)  # 1MB of memory

        # Fill a smaller portion of memory (e.g., 4KB) with a simple ADD instruction: ADD x1, x2, x3
        # 0x003100B3
        instruction = 0x003100B3
        instruction_bytes = instruction.to_bytes(4, 'little')
        for i in range(0, 4 * 1024, 4): # Fill first 4KB
            self.memory[i:i+4] = instruction_bytes

        # Initialize registers for the ADD instruction
        self.registers[2] = 10
        self.registers[3] = 20

    def _read_word(self, address):
        return int.from_bytes(self.memory[address:address+4], 'little')

    def _decode_r_type_instruction(self, instruction):
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        funct7 = (instruction >> 25) & 0x7F
        return opcode, rd, funct3, rs1, rs2, funct7

    def _execute_alu_instruction(self, funct3, rd, rs1, rs2, funct7):
        if funct3 == FUNCT3_ADD and funct7 == FUNCT7_ADD:
            if rd != 0: # x0 is hardwired to zero
                self.registers[rd] = alu.add(self.registers[rs1], self.registers[rs2])
        else:
            raise ValueError(f"Unsupported ALU instruction: funct3={funct3}, funct7={funct7}")

    def execute_instruction(self):
        instruction = self._read_word(self.pc)
        opcode = instruction & 0x7F

        if opcode == OPCODE_R_TYPE:
            opcode, rd, funct3, rs1, rs2, funct7 = self._decode_r_type_instruction(instruction)
            self._execute_alu_instruction(funct3, rd, rs1, rs2, funct7)
        else:
            raise ValueError(f"Unsupported opcode: {opcode}")
        
        self.pc += 4

