import math

import pytest

from src.simulator.memory import Bus, CacheConfig, DRAM, DRAMConfig, MemorySystem, SPM

@pytest.fixture
def spm():
    return SPM(size_kb=4)

@pytest.fixture
def bus():
    bus = Bus()
    bus.devices = {}
    return bus


@pytest.fixture
def dram():
    config = DRAMConfig(banks=4, row_size=128, line_size=16, t_rp=10, t_rcd=6, t_cas=3)
    return DRAM(config)

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
    assert exception_raised  # Write 8 bytes, but only 4 bytes left in device


def test_bus_request_single_transfer():
    bus = Bus(slice_bytes=16, bandwidth_bytes_per_cycle=8, grant_latency=2)

    bus.sync_time(0)
    grant_at, done_at = bus.request(master_id=0, bytes=32)

    assert grant_at == 0
    assert done_at == 6  # grant 0 + latency 2 + transfer 4

    completed = bus.completed_requests()
    assert len(completed) == 1
    request = completed[0]
    assert request.start_at == 2
    assert request.transfer_cycles == 4

    metrics = bus.metrics
    assert metrics.average_wait_cycles() == pytest.approx(0.0)
    assert metrics.average_transfer_cycles() == pytest.approx(4.0)
    assert metrics.max_queue_depth == 1


def test_bus_round_robin_fairness():
    bus = Bus(slice_bytes=16, bandwidth_bytes_per_cycle=16, grant_latency=1)

    bus.sync_time(0)
    grant0, done0 = bus.request(master_id=0, bytes=16)
    grant1, done1 = bus.request(master_id=1, bytes=16, request_at=0)
    grant2, done2 = bus.request(master_id=0, bytes=16, request_at=0)

    assert (grant0, done0) == (0, 2)
    assert (grant1, done1) == (2, 4)
    assert (grant2, done2) == (4, 6)

    metrics = bus.metrics
    assert metrics.average_wait_cycles() == pytest.approx((0 + 2 + 4) / 3)
    assert metrics.average_transfer_cycles() == pytest.approx(1.0)
    assert metrics.average_queue_depth() == pytest.approx((1 + 2 + 3) / 3)
    assert metrics.max_queue_depth == 3


def test_bus_idle_gap_respected():
    bus = Bus(slice_bytes=16, bandwidth_bytes_per_cycle=16, grant_latency=1)

    bus.sync_time(0)
    bus.request(master_id=0, bytes=16)
    bus.sync_time(10)
    grant, done = bus.request(master_id=0, bytes=16)

    assert grant == 10
    assert done == 12

    metrics = bus.metrics
    assert metrics.completed_requests == 2
    assert metrics.average_wait_cycles() == pytest.approx((0 + 0) / 2)


def test_dram_row_hit_and_miss_latency(dram):
    first_done = dram.access(address=0, size=32, request_time=0)
    same_bank_addr = dram.config.line_size * dram.config.banks
    second_done = dram.access(address=same_bank_addr, size=32, request_time=first_done)

    transfer_cycles = math.ceil(32 / dram.config.data_bytes_per_cycle)
    assert first_done - 0 == dram.config.t_rp + dram.config.t_rcd + dram.config.t_cas + transfer_cycles
    assert second_done - first_done == dram.config.t_cas + transfer_cycles


def test_dram_bank_mapping_round_robin(dram):
    banks = dram.config.banks
    line = dram.config.line_size
    observed = [dram.map_address(i * line)[0] for i in range(banks * 2)]
    assert observed[:banks] == list(range(banks))
    assert observed[banks:] == list(range(banks))


def test_dram_config_validation():
    with pytest.raises(ValueError):
        DRAMConfig(banks=0)
    with pytest.raises(ValueError):
        DRAMConfig(row_size=0)
    with pytest.raises(ValueError):
        DRAMConfig(line_size=0)
    with pytest.raises(ValueError):
        DRAMConfig(t_rp=-1)
    with pytest.raises(ValueError):
        DRAMConfig(data_bytes_per_cycle=0)


def test_memory_system_cache_hit_latency():
    bus = Bus(slice_bytes=64, bandwidth_bytes_per_cycle=64, grant_latency=1)
    l1 = CacheConfig(name="L1", size_bytes=64, line_size=64, associativity=1, hit_latency=3)
    l2 = CacheConfig(name="L2", size_bytes=128, line_size=64, associativity=1, hit_latency=9)
    dram_cfg = DRAMConfig(banks=2, row_size=256, line_size=64, t_rp=2, t_rcd=2, t_cas=2, data_bytes_per_cycle=64)
    memory = MemorySystem(bus, l1_config=l1, l2_config=l2, dram_config=dram_cfg)

    miss_done = memory.load(address=0x0, size=4, request_time=0, master_id=0)
    hit_done = memory.load(address=0x0, size=4, request_time=miss_done, master_id=0)

    assert hit_done - miss_done == l1.hit_latency
    stats = memory.cache_stats()
    assert stats["L1"]["hits"] == 1
    assert stats["L1"]["misses"] == 1
    metrics = memory.memory_metrics()
    assert metrics["total_requests"] == 2
    assert metrics["load_requests"] == 2
    assert metrics["average_latency_cycles"] >= 0


def test_memory_system_l1_miss_l2_hit_latency_accounts_for_front_penalty():
    bus = Bus(slice_bytes=64, bandwidth_bytes_per_cycle=64, grant_latency=0)
    l1 = CacheConfig(name="L1", size_bytes=64, line_size=64, associativity=1, hit_latency=1)
    l2 = CacheConfig(name="L2", size_bytes=128, line_size=64, associativity=1, hit_latency=10)
    dram_cfg = DRAMConfig(
        banks=1,
        row_size=64,
        line_size=64,
        t_rp=0,
        t_rcd=0,
        t_cas=0,
        data_bytes_per_cycle=64,
    )
    memory = MemorySystem(bus, l1_config=l1, l2_config=l2, dram_config=dram_cfg)

    aligned_address = 0
    l2_cache = memory._caches[1]
    index = (aligned_address // l2.line_size) % l2_cache.num_sets
    l2_cache.insert(index, aligned_address)

    done_at = memory.load(address=aligned_address, size=4, request_time=0, master_id=0)

    expected_latency = l1.hit_latency + l2.hit_latency + l1.hit_latency
    assert done_at == expected_latency

    stats = memory.cache_stats()
    assert stats["L1"]["hits"] == 0
    assert stats["L1"]["misses"] == 1
    assert stats["L2"]["hits"] == 1
    assert stats["L2"]["misses"] == 0
    assert bus.metrics.completed_requests == 0


def test_memory_system_writeback_on_eviction():
    bus = Bus(slice_bytes=16, bandwidth_bytes_per_cycle=16, grant_latency=0)
    l1 = CacheConfig(
        name="L1",
        size_bytes=32,
        line_size=16,
        associativity=1,
        hit_latency=1,
        write_back=True,
    )
    l2 = CacheConfig(
        name="L2",
        size_bytes=64,
        line_size=16,
        associativity=1,
        hit_latency=4,
        write_back=True,
    )
    dram_cfg = DRAMConfig(
        banks=1,
        row_size=64,
        line_size=16,
        t_rp=1,
        t_rcd=1,
        t_cas=1,
        data_bytes_per_cycle=16,
    )
    memory = MemorySystem(bus, l1_config=l1, l2_config=l2, dram_config=dram_cfg)

    done = memory.store(address=0, size=4, request_time=0, master_id=0)
    done = memory.store(address=32, size=4, request_time=done, master_id=0)
    memory.store(address=64, size=4, request_time=done, master_id=0)

    metrics = bus.metrics
    assert metrics.completed_requests == 4
    stats = memory.cache_stats()
    assert stats["L1"]["hits"] == 0
    assert stats["L1"]["misses"] == 3
    assert stats["L2"]["hits"] == 2
    assert stats["L2"]["misses"] == 3
    mem_metrics = memory.memory_metrics()
    assert mem_metrics["total_requests"] == 3
    assert mem_metrics["store_requests"] == 3
