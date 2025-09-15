import pytest
import numpy as np
from src.npu.model import NPU

@pytest.fixture
def npu():
    return NPU(pool_size=5, max_array_size=(10, 10))

def test_v_add(npu):
    a = np.array([1, 2, 3])
    b = np.array([4, 5, 6])
    result = npu.v_add(a, b)
    assert np.array_equal(result, np.array([5, 7, 9]))
    npu._return_array_to_pool(result)

def test_v_sub(npu):
    a = np.array([4, 5, 6])
    b = np.array([1, 2, 3])
    result = npu.v_sub(a, b)
    assert np.array_equal(result, np.array([3, 3, 3]))
    npu._return_array_to_pool(result)

def test_v_mul(npu):
    a = np.array([1, 2, 3])
    b = np.array([4, 5, 6])
    result = npu.v_mul(a, b)
    assert np.array_equal(result, np.array([4, 10, 18]))
    npu._return_array_to_pool(result)

def test_v_div(npu):
    a = np.array([4, 10, 18])
    b = np.array([2, 5, 6])
    result = npu.v_div(a, b)
    assert np.array_equal(result, np.array([2, 2, 3]))
    npu._return_array_to_pool(result)

def test_execute_operation_v_add(npu):
    add_op = {"type": "v_add", "operands": [np.array([1, 1, 1]), np.array([2, 2, 2])]}
    result = npu.execute_operation(add_op)
    assert np.array_equal(result, np.array([3, 3, 3]))
    npu._return_array_to_pool(result)

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

def test_array_pooling(npu):
    initial_pool_size = len(npu._array_pool)
    assert initial_pool_size == 5

    # Get an array from the pool
    arr1 = npu._get_array_from_pool((10, 10))
    assert len(npu._array_pool) == initial_pool_size - 1

    # Get another array
    arr2 = npu._get_array_from_pool((10, 10))
    assert len(npu._array_pool) == initial_pool_size - 2

    # Return arrays to the pool
    npu._return_array_to_pool(arr1)
    assert len(npu._array_pool) == initial_pool_size - 1
    npu._return_array_to_pool(arr2)
    assert len(npu._array_pool) == initial_pool_size

    # Test getting an array of a different shape
    arr3 = npu._get_array_from_pool((5, 5))
    assert arr3.shape == (5, 5)
    # Pool size should not change as a new array is created
    assert len(npu._array_pool) == initial_pool_size

    # Test returning an array when the pool is full
    npu._return_array_to_pool(arr3) # arr3 is not from the pool
    assert len(npu._array_pool) == initial_pool_size + 1 # It will be added

    # Now the pool is over capacity, returning another should not add it
    arr4 = npu._get_array_from_pool((10,10))
    npu._return_array_to_pool(arr4)
    npu._return_array_to_pool(np.zeros((2,2))) #This should not be added
    assert len(npu._array_pool) <= 10 # Check against max pool size in model.py