import pytest
import numpy as np
from src.risc_v.instructions import alu, control_flow, memory
from src.npu.model import NPU
from src.simulator.memory import Bus


class MockState:
    def __init__(self, pc: int):
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
def bus():
    memory_size = 1024
    dram = bytearray(memory_size)
    mem_bus = Bus()
    mem_bus.add_device("dram", dram, 0, memory_size - 1)
    return mem_bus


def test_ld_benchmark(benchmark, bus):
    benchmark(memory.ld, bus, 0)


def test_sd_benchmark(benchmark, bus):
    benchmark(memory.sd, bus, 0, 12345)


def test_lw_benchmark(benchmark, bus):
    benchmark(memory.lw, bus, 8)


def test_sw_benchmark(benchmark, bus):
    benchmark(memory.sw, bus, 8, 6789)


# T026c: Control flow instruction benchmarks

@pytest.fixture
def state():
    return MockState(pc=100)


def test_beq_benchmark(benchmark):
    benchmark(control_flow.beq, 1, 1)

def test_bne_benchmark(benchmark):
    benchmark(control_flow.bne, 1, 2)


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
    safe_b = np.where(b == 0, 1, b)
    benchmark(npu_model.v_div, a, safe_b)
