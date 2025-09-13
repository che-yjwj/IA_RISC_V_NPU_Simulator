class Classifier:
    """
    A simple classifier to determine the complexity of an instruction.
    """
    def __init__(self):
        """
        Initializes the Classifier with a mapping of opcodes to complexity scores.
        """
        self.complexity_map = {
            # ALU instructions
            'ADD': 0.2,
            'SUB': 0.2,
            'AND': 0.2,
            'OR': 0.2,
            'XOR': 0.2,

            # Control flow instructions
            'BEQ': 0.5,
            'BNE': 0.5,
            'JAL': 0.5,
            'JALR': 0.5,

            # Memory access instructions
            'LD': 0.8,
            'SD': 0.8,
            'LW': 0.8,
            'SW': 0.8,
        }

    def classify(self, instruction):
        """
        Classifies the given instruction and returns a complexity score.

        This implementation assumes the instruction is a dictionary with an 'opcode' key.

        Args:
            instruction (dict): The instruction to classify, e.g., {'opcode': 'ADD'}.

        Returns:
            float: The complexity score (0.0 to 1.0), or 0.1 for unknown opcodes.
        """
        opcode = instruction.get('opcode')
        return self.complexity_map.get(opcode, 0.1)
