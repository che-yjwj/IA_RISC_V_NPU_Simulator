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

def test_execute_operation(npu):
    add_op = {"type": "v_add", "operands": [np.array([1, 1, 1]), np.array([2, 2, 2])]}
    result = npu.execute_operation(add_op)
    assert np.array_equal(result, np.array([3, 3, 3]))
