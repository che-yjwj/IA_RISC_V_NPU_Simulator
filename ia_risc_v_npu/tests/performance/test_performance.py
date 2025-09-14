import pytest
import numpy as np
from src.risc_v.instructions import alu, control_flow, memory
from src.npu.model import NPU

# Mock state for control flow instructions
class MockState:
    def __init__(self, pc):
        self.pc = pc

# T026a: ALU instruction benchmarks
def test_add_benchmark(benchmark):
    benchmark(alu.add, 1, 2)

def test_sub_benchmark(benchmark):
    benchmark(alu.sub, 5, 3)

def test_and_benchmark(benchmark):
    benchmark(alu.and_, 5, 3)

def test_or_benchmark(benchmark):
    benchmark(alu.or_, 5, 3)

def test_xor_benchmark(benchmark):
    benchmark(alu.xor, 5, 3)

# T026b: Memory access instruction benchmarks
@pytest.fixture
def mem():
    return bytearray(1024)

def test_ld_benchmark(benchmark, mem):
    benchmark(memory.ld, mem, 0)

def test_sd_benchmark(benchmark, mem):
    benchmark(memory.sd, mem, 0, 12345)

def test_lw_benchmark(benchmark, mem):
    benchmark(memory.lw, mem, 8)

def test_sw_benchmark(benchmark, mem):
    benchmark(memory.sw, mem, 8, 6789)

# T026c: Control flow instruction benchmarks
@pytest.fixture
def state():
    return MockState(pc=100)

def test_beq_benchmark(benchmark, state):
    benchmark(control_flow.beq, state, 1, 1, 20)

def test_bne_benchmark(benchmark, state):
    benchmark(control_flow.bne, state, 1, 2, 20)

def test_jal_benchmark(benchmark, state):
    benchmark(control_flow.jal, state, 40)

def test_jalr_benchmark(benchmark, state):
    benchmark(control_flow.jalr, state, 120, 16)

# T026d: NPU vector operation benchmarks
@pytest.fixture
def npu_model():
    return NPU()

@pytest.fixture
def vectors():
    return np.random.rand(1024), np.random.rand(1024)

def test_npu_v_add_benchmark(benchmark, npu_model, vectors):
    a, b = vectors
    benchmark(npu_model.v_add, a, b)

def test_npu_v_sub_benchmark(benchmark, npu_model, vectors):
    a, b = vectors
    benchmark(npu_model.v_sub, a, b)

def test_npu_v_mul_benchmark(benchmark, npu_model, vectors):
    a, b = vectors
    benchmark(npu_model.v_mul, a, b)

def test_npu_v_div_benchmark(benchmark, npu_model, vectors):
    a, b = vectors
    # Ensure no division by zero
    safe_b = np.where(b == 0, 1, b)
    benchmark(npu_model.v_div, a, safe_b)