import numpy as np

class NPU:
    def __init__(self):
        self.internal_registers = {}
        self.execution_status = "idle"

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
        
        if op_type == "v_add":
            return self.v_add(operands[0], operands[1])
        elif op_type == "v_sub":
            return self.v_sub(operands[0], operands[1])
        elif op_type == "v_mul":
            return self.v_mul(operands[0], operands[1])
        elif op_type == "v_div":
            return self.v_div(operands[0], operands[1])
        else:
            # Handle other operations or raise an error
            pass
