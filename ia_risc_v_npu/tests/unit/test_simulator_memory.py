import pytest
from src.simulator.memory import SPM, Bus

@pytest.fixture
def spm():
    return SPM(size_kb=4)

@pytest.fixture
def bus():
    return Bus()

def test_spm_initialization(spm):
    assert spm.size == 4 * 1024
    assert len(spm.memory) == 4 * 1024

def test_spm_read_write(spm):
    data_to_write = b'\xde\xad\xbe\xef'
    spm.write(0, data_to_write)
    read_data = spm.read(0, len(data_to_write))
    assert read_data == data_to_write

def test_bus_add_device(bus, spm):
    bus.add_device("spm", spm, 0x1000, 0x1FFF)
    assert "spm" in bus.devices
    assert bus.devices["spm"]["device"] == spm

def test_bus_read_write(bus, spm):
    bus.add_device("spm", spm, 0x1000, 0x1FFF)
    data_to_write = b'\xca\xfe\xba\xbe'
    bus.write(0x1010, data_to_write)
    read_data = bus.read(0x1010, len(data_to_write))
    assert read_data == data_to_write

def test_bus_invalid_address(bus):
    with pytest.raises(MemoryError):
        bus.read(0x2000, 4)
    with pytest.raises(MemoryError):
        bus.write(0x2000, b'\x00')
