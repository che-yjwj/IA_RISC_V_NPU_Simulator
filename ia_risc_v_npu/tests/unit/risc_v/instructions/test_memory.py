import pytest
from src.risc_v.instructions.memory import ld, sd, lw, sw

# This is a simplified representation of memory for testing purposes.
memory = bytearray(1024)

def test_ld():
    # Store a 64-bit value (8 bytes) at address 0
    memory[0:8] = (1234567890123456789).to_bytes(8, 'little')
    assert ld(memory, 0) == 1234567890123456789

def test_sd():
    sd(memory, 8, 9876543210987654321)
    assert int.from_bytes(memory[8:16], 'little') == 9876543210987654321

def test_lw():
    # Store a 32-bit value (4 bytes) at address 16
    memory[16:20] = (1234567890).to_bytes(4, 'little')
    assert lw(memory, 16) == 1234567890

def test_sw():
    sw(memory, 20, 987654321)
    assert int.from_bytes(memory[20:24], 'little') == 987654321
