import numpy as np

class NPU:
    def __init__(self, pool_size=10, max_array_size=(1024, 1024)):
        self.internal_registers = {}
        self.execution_status = "idle"
        self._operations = {
            "v_add": self.v_add,
            "v_sub": self.v_sub,
            "v_mul": self.v_mul,
            "v_div": self.v_div,
        }
        self._array_pool = [np.zeros(max_array_size, dtype=np.float32) for _ in range(pool_size)]

    def _get_array_from_pool(self, shape):
        # Find a suitable array in the pool
        for i, arr in enumerate(self._array_pool):
            if arr.shape == shape and arr.dtype == np.float32:
                return self._array_pool.pop(i)
        # If no suitable array is found, create a new one
        return np.zeros(shape, dtype=np.float32)

    def _return_array_to_pool(self, arr):
        # Return array to the pool if there is space
        if len(self._array_pool) < 10: # pool_size
            self._array_pool.append(arr)

    def v_add(self, a, b):
        result = self._get_array_from_pool(a.shape)
        np.add(a, b, out=result)
        return result

    def v_sub(self, a, b):
        result = self._get_array_from_pool(a.shape)
        np.subtract(a, b, out=result)
        return result

    def v_mul(self, a, b):
        result = self._get_array_from_pool(a.shape)
        np.multiply(a, b, out=result)
        return result

    def v_div(self, a, b):
        result = self._get_array_from_pool(a.shape)
        np.divide(a, b, out=result)
        return result

    def execute_operation(self, operation):
        op_type = operation.get("type")
        operands = operation.get("operands")

        if op_type not in self._operations:
            raise ValueError(f"Unknown NPU operation type: {op_type}")

        if not isinstance(operands, list) or len(operands) != 2:
            raise ValueError(f"Invalid or insufficient operands for operation {op_type}. Expected 2, got {len(operands) if isinstance(operands, list) else 'none'}")

        op_func = self._operations[op_type]
        result = op_func(operands[0], operands[1])
        # The caller is responsible for returning the result array to the pool
        return result