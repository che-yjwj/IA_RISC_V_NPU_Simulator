import pytest
from src.risc_v.instructions.memory import ld, sd, lw, sw
from src.simulator.memory import SPM

# This is a simplified representation of memory for testing purposes.
@pytest.fixture
def memory():
    spm = SPM(size_kb=1) # 1KB memory
    # Initialize with some data for reads
    for i in range(0, 1024, 4):
        spm.write(i, (i // 4).to_bytes(4, 'little'))
    return spm

def test_ld(memory):
    # Store a 64-bit value (8 bytes) at address 0
    memory.write(0, (1234567890123456789).to_bytes(8, 'little'))
    assert ld(memory, 0) == 1234567890123456789

def test_sd(memory):
    sd(memory, 8, 0x123456789ABCDEF0)
    assert int.from_bytes(memory.read(8, 8), 'little') == 0x123456789ABCDEF0

def test_lw(memory):
    # Store a 32-bit value (4 bytes) at address 16
    memory.write(16, (1234567890).to_bytes(4, 'little'))
    assert lw(memory, 16) == 1234567890

def test_sw(memory):
    sw(memory, 20, 987654321)
    assert int.from_bytes(memory.read(20, 4), 'little') == 987654321
