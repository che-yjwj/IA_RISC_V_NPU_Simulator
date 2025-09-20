import pytest
from src.simulator.memory import SPM, Bus

@pytest.fixture
def spm():
    return SPM(size_kb=4)

@pytest.fixture
def bus():
    bus = Bus()
    bus.devices = {}
    return bus

def test_spm_initialization(spm):
    assert spm.size == 4 * 1024
    assert len(spm.memory) == 4 * 1024

def test_spm_read_write(spm):
    data_to_write = b'\xde\xad\xbe\xef'
    spm.write(0, data_to_write)
    read_data = spm.read(0, len(data_to_write))
    assert read_data == data_to_write

def test_spm_read_out_of_bounds(spm):
    with pytest.raises(IndexError, match="SPM read out of bounds"):
        spm.read(spm.size - 2, 4) # Read 4 bytes, but only 2 bytes left
    with pytest.raises(IndexError, match="SPM read out of bounds"):
        spm.read(spm.size, 1) # Read from exact end of memory

def test_spm_write_out_of_bounds(spm):
    data_to_write = b'\x00\x00\x00\x00'
    with pytest.raises(IndexError, match="SPM write out of bounds"):
        spm.write(spm.size - 2, data_to_write) # Write 4 bytes, but only 2 bytes left
    with pytest.raises(IndexError, match="SPM write out of bounds"):
        spm.write(spm.size, data_to_write) # Write from exact end of memory

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
    exception_raised = False
    try:
        bus.read(0x2000, 4)
    except MemoryError:
        exception_raised = True
    assert exception_raised

    exception_raised = False
    try:
        bus.write(0x2000, b'\x00')
    except MemoryError:
        exception_raised = True
    assert exception_raised

def test_bus_cross_boundary_read(bus, spm):
    bus.add_device("spm", spm, 0x1000, 0x1FFF)
    exception_raised = False
    try:
        bus.read(0x1FFC, 8)
    except MemoryError:
        exception_raised = True
    assert exception_raised

def test_bus_cross_boundary_write(bus, spm):
    bus.add_device("spm", spm, 0x1000, 0x1FFF)
    data_to_write = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    exception_raised = False
    try:
        bus.write(0x1FFC, data_to_write)
    except MemoryError:
        exception_raised = True
    assert exception_raised # Write 8 bytes, but only 4 bytes left in device
