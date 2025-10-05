from contextlib import contextmanager

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
        self.pool_size = pool_size
        self._array_pool = [
            np.zeros(max_array_size, dtype=np.float32) for _ in range(pool_size)
        ]

    def _get_array_from_pool(self, shape):
        # Find a suitable array in the pool
        for i, arr in enumerate(self._array_pool):
            if arr.shape == shape and arr.dtype == np.float32:
                return self._array_pool.pop(i)
        # If no suitable array is found, create a new one
        return np.zeros(shape, dtype=np.float32)

    def return_array_to_pool(self, arr):
        # Return array to the pool if there is space
        if len(self._array_pool) < self.pool_size:
            self._array_pool.append(arr)

    @contextmanager
    def get_pooled_array(self, shape):
        arr = self._get_array_from_pool(shape)
        try:
            yield arr
        finally:
            self.return_array_to_pool(arr)

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
            got = len(operands) if isinstance(operands, list) else "none"
            raise ValueError(
                f"Invalid or insufficient operands for operation {op_type}. "
                f"Expected 2, got {got}"
            )

        op_func = self._operations[op_type]
        return op_func(operands[0], operands[1])
