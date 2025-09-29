"""Program image structures shared between CLI and simulator loader."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(slots=True)
class ProgramSegment:
    """Loadable segment description extracted from an ELF file."""

    address: int
    data: bytes
    mem_size: int

    def __post_init__(self) -> None:
        if self.address < 0:
            raise ValueError("segment address must be non-negative")
        if self.mem_size < 0:
            raise ValueError("segment mem_size must be non-negative")
        if self.mem_size < len(self.data):
            raise ValueError("segment mem_size must cover data length")


@dataclass(slots=True)
class ProgramImage:
    """Complete program payload ready to be loaded into simulator memory."""

    instructions: List[int]
    text_size: int
    entry_point: int
    segments: Sequence[ProgramSegment]

    def __post_init__(self) -> None:
        if self.entry_point < 0:
            raise ValueError("entry_point must be non-negative")
        if self.text_size < 0:
            raise ValueError("text_size must be non-negative")
        if not self.segments:
            raise ValueError("at least one segment is required")


__all__ = ["ProgramImage", "ProgramSegment"]
