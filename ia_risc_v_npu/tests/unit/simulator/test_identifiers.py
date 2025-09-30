import pytest

from src.npu.cluster import NPUCluster
from src.simulator.identifiers import (
    BusMasterID,
    DRAM,
    MEMORY_REGIONS,
    MMIO,
    SPM,
)
from src.simulator.memory import Bus


def test_bus_master_ids_are_stable():
    assert int(BusMasterID.CPU) == 0
    assert int(BusMasterID.NPU_DMA) == 1


def test_memory_regions_are_consistent():
    for region in (DRAM, SPM, MMIO):
        assert region.end == region.base + region.size - 1
        assert MEMORY_REGIONS[region.name] == region


def test_bus_accepts_enum_master_id():
    bus = Bus(slice_bytes=16, bandwidth_bytes_per_cycle=16, grant_latency=1)
    grant, done = bus.request(master_id=BusMasterID.CPU, bytes=16)
    assert grant == 0
    assert done == 2


def test_npu_cluster_accepts_enum_master_id():
    bus = Bus()
    cluster = NPUCluster(bus, dma_master_id=BusMasterID.NPU_DMA)
    assert cluster.dma_master_id == int(BusMasterID.NPU_DMA)
