"""Lightweight helpers for estimating bus transfer timelines."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping


@dataclass(slots=True)
class BusTimingModel:
    """Approximate the time required to service bus transfers."""

    slice_bytes: int
    bandwidth_bytes_per_cycle: int
    grant_latency: int

    @classmethod
    def from_config(cls, config: Mapping[str, int]) -> "BusTimingModel":
        return cls(
            slice_bytes=int(config.get("slice_bytes", 32)),
            bandwidth_bytes_per_cycle=int(config.get("bandwidth_bytes_per_cycle", 16)),
            grant_latency=int(config.get("grant_latency", 1)),
        )

    def estimate_cycles(self, size_bytes: int) -> int:
        if size_bytes <= 0:
            return 0
        full_slices, remainder = divmod(size_bytes, self.slice_bytes)
        slice_cycles = max(
            1, math.ceil(self.slice_bytes / self.bandwidth_bytes_per_cycle)
        )
        total = full_slices * slice_cycles
        if remainder:
            total += math.ceil(remainder / self.bandwidth_bytes_per_cycle)
        return self.grant_latency + total

    def completion_cycle(self, grant_at: int, size_bytes: int) -> int:
        return grant_at + self.estimate_cycles(size_bytes)
