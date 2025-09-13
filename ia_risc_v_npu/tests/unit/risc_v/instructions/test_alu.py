import pytest
from src.risc_v.instructions.alu import add, sub, and_, or_, xor

def test_add():
    assert add(1, 2) == 3

def test_sub():
    assert sub(2, 1) == 1

def test_and():
    assert and_(0b1010, 0b1100) == 0b1000

def test_or():
    assert or_(0b1010, 0b1100) == 0b1110

def test_xor():
    assert xor(0b1010, 0b1100) == 0b0110
