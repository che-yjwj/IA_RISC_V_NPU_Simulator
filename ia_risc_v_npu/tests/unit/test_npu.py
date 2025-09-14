import pytest
import numpy as np
from src.npu.model import NPU

@pytest.fixture
def npu():
    return NPU()

def test_v_add(npu):
    a = np.array([1, 2, 3])
    b = np.array([4, 5, 6])
    result = npu.v_add(a, b)
    assert np.array_equal(result, np.array([5, 7, 9]))

def test_v_sub(npu):
    a = np.array([4, 5, 6])
    b = np.array([1, 2, 3])
    result = npu.v_sub(a, b)
    assert np.array_equal(result, np.array([3, 3, 3]))

def test_v_mul(npu):
    a = np.array([1, 2, 3])
    b = np.array([4, 5, 6])
    result = npu.v_mul(a, b)
    assert np.array_equal(result, np.array([4, 10, 18]))

def test_v_div(npu):
    a = np.array([4, 10, 18])
    b = np.array([2, 5, 6])
    result = npu.v_div(a, b)
    assert np.array_equal(result, np.array([2, 2, 3]))

def test_execute_operation_v_add(npu):
    add_op = {"type": "v_add", "operands": [np.array([1, 1, 1]), np.array([2, 2, 2])]}
    result = npu.execute_operation(add_op)
    assert np.array_equal(result, np.array([3, 3, 3]))

def test_execute_operation_unknown_type(npu):
    unknown_op = {"type": "v_unknown", "operands": [np.array([1]), np.array([2])]}
    with pytest.raises(ValueError, match="Unknown NPU operation type: v_unknown"):
        npu.execute_operation(unknown_op)

def test_execute_operation_invalid_operands(npu):
    invalid_op = {"type": "v_add", "operands": [np.array([1])]}
    with pytest.raises(ValueError, match="Invalid or insufficient operands"):
        npu.execute_operation(invalid_op)

def test_execute_operation_missing_operands(npu):
    missing_op = {"type": "v_add"}
    with pytest.raises(ValueError, match="Invalid or insufficient operands"):
        npu.execute_operation(missing_op)
