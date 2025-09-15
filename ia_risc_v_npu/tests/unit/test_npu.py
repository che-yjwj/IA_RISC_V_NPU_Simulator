import pytest
import numpy as np
from src.npu.model import NPU

@pytest.fixture
def npu():
    # Use a small pool size for easier testing
    return NPU(pool_size=2, max_array_size=(3,))

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

def test_array_pooling_with_context_manager(npu):
    initial_pool_size = len(npu._array_pool)
    assert initial_pool_size == 2

    # Use the context manager
    with npu.get_pooled_array((3,)) as arr1:
        assert len(npu._array_pool) == initial_pool_size - 1
        arr1.fill(5)
        assert np.all(arr1 == 5)
    
    # After exiting context, array should be returned to the pool
    assert len(npu._array_pool) == initial_pool_size

    # Test nested context managers
    with npu.get_pooled_array((3,)) as arr1:
        with npu.get_pooled_array((3,)) as arr2:
            assert len(npu._array_pool) == initial_pool_size - 2
    
    assert len(npu._array_pool) == initial_pool_size

def test_pool_overflow(npu):
    initial_pool_size = len(npu._array_pool)
    assert initial_pool_size == 2

    # Exhaust the pool
    arrs = [npu._get_array_from_pool((3,)) for _ in range(initial_pool_size)]
    assert len(npu._array_pool) == 0

    # Get one more array (should be newly created)
    extra_arr = npu._get_array_from_pool((3,))
    assert len(npu._array_pool) == 0

    # Return all arrays
    for arr in arrs:
        npu.return_array_to_pool(arr)
    
    assert len(npu._array_pool) == initial_pool_size

    # Try to return the extra array - should not be added as pool is full
    npu.return_array_to_pool(extra_arr)
    assert len(npu._array_pool) == initial_pool_size
