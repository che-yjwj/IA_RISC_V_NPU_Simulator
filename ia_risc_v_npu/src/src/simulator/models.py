from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class BusRequest:
    master_id: int
    size_bytes: int
    request_at: int
    grant_at: Optional[int] = None
    start_at: Optional[int] = None
    done_at: Optional[int] = None
    transfer_cycles: int = 0


@dataclass
class BusMetrics:
    completed_requests: int = 0
    total_wait_cycles: int = 0
    total_transfer_cycles: int = 0
    total_grant_latency_cycles: int = 0
    cumulative_queue_depth: int = 0
    queue_depth_samples: int = 0
    max_queue_depth: int = 0

    def on_request(self, queue_depth: int) -> None:
        self.queue_depth_samples += 1
        self.cumulative_queue_depth += queue_depth
        if queue_depth > self.max_queue_depth:
            self.max_queue_depth = queue_depth

    def on_grant(
        self, *, wait_cycles: int, grant_latency: int, transfer_cycles: int
    ) -> None:
        self.completed_requests += 1
        self.total_wait_cycles += wait_cycles
        self.total_transfer_cycles += transfer_cycles
        self.total_grant_latency_cycles += grant_latency

    def average_wait_cycles(self) -> float:
        if self.completed_requests == 0:
            return 0.0
        return self.total_wait_cycles / self.completed_requests

    def average_transfer_cycles(self) -> float:
        if self.completed_requests == 0:
            return 0.0
        return self.total_transfer_cycles / self.completed_requests

    def average_queue_depth(self) -> float:
        if self.queue_depth_samples == 0:
            return 0.0
        return self.cumulative_queue_depth / self.queue_depth_samples

    def snapshot(self) -> Dict[str, float | int]:
        return {
            "completed_requests": self.completed_requests,
            "avg_wait_cycles": self.average_wait_cycles(),
            "avg_transfer_cycles": self.average_transfer_cycles(),
            "avg_queue_depth": self.average_queue_depth(),
            "max_queue_depth": self.max_queue_depth,
            "total_wait_cycles": self.total_wait_cycles,
            "total_transfer_cycles": self.total_transfer_cycles,
            "total_grant_latency_cycles": self.total_grant_latency_cycles,
        }


@dataclass(frozen=True)
class CacheConfig:
    """Static cache parameters."""

    name: str
    size_bytes: int
    line_size: int
    associativity: int
    hit_latency: int
    write_back: bool = True
    write_allocate: bool = True

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be greater than zero")
        if self.line_size <= 0:
            raise ValueError("line_size must be greater than zero")
        if self.associativity <= 0:
            raise ValueError("associativity must be greater than zero")
        if self.hit_latency < 0:
            raise ValueError("hit_latency cannot be negative")
        if self.size_bytes % (self.line_size * self.associativity) != 0:
            raise ValueError(
                "Cache size must be divisible by line_size * associativity"
            )


@dataclass
class CacheLine:
    tag: int = -1
    valid: bool = False
    dirty: bool = False
    last_used: int = 0


@dataclass(frozen=True)
class CacheEviction:
    address: int
    dirty: bool


@dataclass(frozen=True)
class DRAMConfig:
    """Static configuration for the DRAM timing model."""

    banks: int = 8
    row_size: int = 4096
    line_size: int = 64
    t_rp: int = 12  # Precharge
    t_rcd: int = 12  # Activate to read/write
    t_cas: int = 12  # Column access
    data_bytes_per_cycle: int = 16  # Burst transfer throughput

    def __post_init__(self) -> None:
        if self.banks <= 0:
            raise ValueError("banks must be greater than zero")
        if self.row_size <= 0:
            raise ValueError("row_size must be greater than zero")
        if self.line_size <= 0:
            raise ValueError("line_size must be greater than zero")
        if self.t_rp < 0 or self.t_rcd < 0 or self.t_cas < 0:
            raise ValueError("DRAM timing parameters cannot be negative")
        if self.data_bytes_per_cycle <= 0:
            raise ValueError("data_bytes_per_cycle must be greater than zero")


@dataclass
class DRAMMetrics:
    access_count: int = 0
    row_hits: int = 0
    row_misses: int = 0
    total_latency_cycles: int = 0

    def on_access(self, *, row_hit: bool, latency: int) -> None:
        self.access_count += 1
        if row_hit:
            self.row_hits += 1
        else:
            self.row_misses += 1
        self.total_latency_cycles += latency

    def average_latency(self) -> float:
        if self.access_count == 0:
            return 0.0
        return self.total_latency_cycles / self.access_count

    def snapshot(self) -> Dict[str, float | int]:
        return {
            "access_count": self.access_count,
            "row_hits": self.row_hits,
            "row_misses": self.row_misses,
            "row_hit_rate": (
                self.row_hits / self.access_count if self.access_count > 0 else 0.0
            ),
            "total_latency_cycles": self.total_latency_cycles,
            "average_latency": self.average_latency(),
        }
