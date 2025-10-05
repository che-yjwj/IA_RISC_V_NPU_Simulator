"""Shared identifiers for bus masters and memory-mapped regions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class BusMasterID(IntEnum):
    """Logical master identifiers on the shared bus."""

    CPU = 0
    NPU_DMA = 1


@dataclass(frozen=True)
class MemoryRegion:
    """Inclusive address range for a memory-mapped component."""

    name: str
    base: int
    size: int

    @property
    def end(self) -> int:
        """Return the inclusive end address."""

        return self.base + self.size - 1


DRAM = MemoryRegion(name="dram", base=0x0000_0000, size=1024 * 1024)
SPM = MemoryRegion(name="spm", base=0x1000_0000, size=64 * 1024)
MMIO = MemoryRegion(name="mmio", base=0x2000_0000, size=0x10000)

MEMORY_REGIONS = {
    DRAM.name: DRAM,
    SPM.name: SPM,
    MMIO.name: MMIO,
}

__all__ = [
    "BusMasterID",
    "MemoryRegion",
    "DRAM",
    "SPM",
    "MMIO",
    "MEMORY_REGIONS",
]
