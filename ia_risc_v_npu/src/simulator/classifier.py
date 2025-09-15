from typing import Any, Dict, List
from collections import deque

class Classifier:
    """
    A classifier to determine the complexity of instruction sequences and detect Regions of Interest (ROI).
    """
    _COMPLEXITY_MAP: Dict[str, float] = {
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
    _DEFAULT_COMPLEXITY: float = 0.1
    _MEMORY_OPCODES = {'LD', 'SD', 'LW', 'SW'}

    def __init__(self, window_size=10):
        self.instruction_window: deque = deque(maxlen=window_size)

    def classify(self, instruction: Dict[str, Any]) -> float:
        """
        Classifies the given instruction and updates the ROI score based on the instruction window.

        Args:
            instruction (dict): The instruction to classify, e.g., {'opcode': 'ADD'}.

        Returns:
            float: The ROI score (0.0 to 1.0).
        """
        self.instruction_window.append(instruction)
        
        # Calculate base complexity
        opcode = instruction.get('opcode')
        base_complexity = self._COMPLEXITY_MAP.get(opcode, self._DEFAULT_COMPLEXITY)

        # Advanced ROI detection based on pattern
        roi_score = self._detect_memory_pattern()

        return max(base_complexity, roi_score)

    def _detect_memory_pattern(self) -> float:
        """
        Detects consecutive memory access patterns in the instruction window.
        Returns a score based on the density of memory operations.
        """
        if not self.instruction_window:
            return 0.0

        memory_op_count = sum(
            1 for inst in self.instruction_window if inst.get('opcode') in self._MEMORY_OPCODES
        )
        
        # Score based on the ratio of memory operations in the window
        return float(memory_op_count) / len(self.instruction_window)