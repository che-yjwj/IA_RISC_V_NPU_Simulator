import pytest
from src.risc_v.instructions.alu import add

def test_add_benchmark(benchmark):
    benchmark(add, 1, 2)
