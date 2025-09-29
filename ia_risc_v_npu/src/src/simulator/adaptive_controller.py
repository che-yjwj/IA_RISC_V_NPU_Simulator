class FidelityController:
    """
    Determines the fidelity level for instruction simulation based on complexity.
    """
    def __init__(self, threshold=0.5):
        """
        Initializes the FidelityController with a complexity threshold.

        Args:
            threshold (float): The complexity threshold to switch to Lev1.
        """
        self.threshold = threshold

    def should_use_lev1(self, instruction_result):
        """
        Determines if the simulation should use the high-fidelity level (Lev1).

        Args:
            instruction_result: An object with a 'complexity' attribute.

        Returns:
            bool: True if complexity is above the threshold, False otherwise.
        """
        return instruction_result.complexity > self.threshold
