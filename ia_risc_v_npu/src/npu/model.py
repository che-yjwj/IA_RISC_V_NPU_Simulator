import numpy as np

class NPU:
    def __init__(self):
        self.internal_registers = {}
        self.execution_status = "idle"
        self._operations = {
            "v_add": self.v_add,
            "v_sub": self.v_sub,
            "v_mul": self.v_mul,
            "v_div": self.v_div,
        }

    def v_add(self, a, b):
        return np.add(a, b)

    def v_sub(self, a, b):
        return np.subtract(a, b)

    def v_mul(self, a, b):
        return np.multiply(a, b)

    def v_div(self, a, b):
        return np.divide(a, b)

    def execute_operation(self, operation):
        op_type = operation.get("type")
        operands = operation.get("operands")

        if op_type not in self._operations:
            raise ValueError(f"Unknown NPU operation type: {op_type}")

        if not isinstance(operands, list) or len(operands) != 2:
            raise ValueError(f"Invalid or insufficient operands for operation {op_type}. Expected 2, got {len(operands) if isinstance(operands, list) else 'none'}")

        op_func = self._operations[op_type]
        return op_func(operands[0], operands[1])
