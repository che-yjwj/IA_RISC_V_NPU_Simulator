from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from src.simulator.config import DEFAULT_L1_CONFIG, DEFAULT_L2_CONFIG
from src.simulator.devices import SPM as _SPM
from src.simulator.devices import Bus
from src.simulator.models import (
    CacheConfig,
    CacheEviction,
    CacheLine,
    DRAMConfig,
    DRAMMetrics,
)

LOGGER = logging.getLogger(__name__)

# Re-export SPM for backward compatibility with existing imports.
SPM = _SPM


class CacheLevel:
    """Set-associative cache metadata with LRU replacement."""

    def __init__(self, config: CacheConfig) -> None:
        self.config = config
        self.num_sets = self.config.size_bytes // (
            self.config.line_size * self.config.associativity
        )
        if self.num_sets <= 0:
            raise ValueError("Derived number of sets must be positive")

        self.sets: List[List[CacheLine]] = [
            [CacheLine() for _ in range(self.config.associativity)]
            for _ in range(self.num_sets)
        ]
        self._use_counter = 0
        self._hits = 0
        self._misses = 0

    @property
    def hit_latency(self) -> int:
        return self.config.hit_latency

    @property
    def line_size(self) -> int:
        return self.config.line_size

    def stats(self) -> Dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}

    def _index_tag(self, address: int) -> Tuple[int, int]:
        line_addr = address // self.config.line_size
        index = line_addr % self.num_sets
        tag = line_addr // self.num_sets
        return index, tag

    def _compose_address(self, index: int, tag: int) -> int:
        line_addr = tag * self.num_sets + index
        return line_addr * self.config.line_size

    def lookup(self, address: int) -> Tuple[Optional[CacheLine], int]:
        index, tag = self._index_tag(address)
        set_lines = self.sets[index]
        for line in set_lines:
            if line.valid and line.tag == tag:
                self._hits += 1
                self._use_counter += 1
                line.last_used = self._use_counter
                return line, index
        self._misses += 1
        return None, index

    def insert(
        self, index: int, address: int
    ) -> Tuple[CacheLine, Optional[CacheEviction]]:
        set_lines = self.sets[index]
        for line in set_lines:
            if not line.valid:
                target = line
                break
        else:
            target = min(set_lines, key=lambda entry: entry.last_used)

        eviction: Optional[CacheEviction] = None
        if target.valid:
            eviction = CacheEviction(
                address=self._compose_address(index, target.tag),
                dirty=target.dirty,
            )

        _, tag = self._index_tag(address)
        target.tag = tag
        target.valid = True
        target.dirty = False
        self._use_counter += 1
        target.last_used = self._use_counter
        return target, eviction

    def mark_dirty(self, line: CacheLine) -> None:
        if self.config.write_back:
            line.dirty = True

    def reset(self) -> None:
        self._use_counter = 0
        self._hits = 0
        self._misses = 0
        for set_lines in self.sets:
            for line in set_lines:
                line.tag = -1
                line.valid = False
                line.dirty = False
                line.last_used = 0


class DRAM:
    """Simple DRAM timing approximation with bank/row tracking."""

    def __init__(
        self,
        config: Optional[DRAMConfig] = None,
        metrics: Optional[DRAMMetrics] = None,
    ):
        self.config = config or DRAMConfig()
        self.metrics = metrics or DRAMMetrics()
        self.bank_free_at: List[int] = [0] * self.config.banks
        self.row_open: List[Optional[int]] = [None] * self.config.banks
        self._now = 0

    def reset(self) -> None:
        self.bank_free_at = [0] * self.config.banks
        self.row_open = [None] * self.config.banks
        self._now = 0
        self.metrics = self.metrics.__class__()

    def map_address(self, address: int) -> Tuple[int, int]:
        if address < 0:
            raise ValueError("Address must be non-negative")
        line_index = address // max(1, self.config.line_size)
        bank = line_index % self.config.banks
        row = address // self.config.row_size
        return bank, row

    def access(
        self, address: int, size: int, *, request_time: Optional[int] = None
    ) -> int:
        if size <= 0:
            raise ValueError("Size must be positive")

        now = self._now if request_time is None else max(self._now, request_time)
        bank, row = self.map_address(address)

        ready_at = max(now, self.bank_free_at[bank])
        row_hit = self.row_open[bank] == row
        command_latency = (
            self.config.t_cas
            if row_hit
            else self.config.t_rp + self.config.t_rcd + self.config.t_cas
        )
        transfer_cycles = math.ceil(size / self.config.data_bytes_per_cycle)

        done_at = ready_at + command_latency + transfer_cycles
        self.metrics.on_access(row_hit=row_hit, latency=done_at - ready_at)
        self.bank_free_at[bank] = done_at
        self.row_open[bank] = row
        self._now = max(self._now, done_at)
        return done_at


class MemorySystem:
    """Deterministic cache hierarchy with bus/DRAM backing."""

    def __init__(
        self,
        bus: Bus,
        *,
        dram_config: Optional[DRAMConfig] = None,
        l1_config: Optional[CacheConfig] = None,
        l2_config: Optional[CacheConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.bus = bus
        self.dram = DRAM(dram_config)
        self._caches: List[CacheLevel] = []
        if l1_config is None:
            l1_config = DEFAULT_L1_CONFIG
        if l2_config is None:
            l2_config = DEFAULT_L2_CONFIG

        self._caches.append(CacheLevel(l1_config))
        self._caches.append(CacheLevel(l2_config))
        self._now = 0
        self._reset_stats()
        self.logger = logger or LOGGER

    def reset(self) -> None:
        self.dram.reset()
        for cache in self._caches:
            cache.reset()
        self._now = 0
        self._reset_stats()

    def cache_stats(self) -> Dict[str, Dict[str, int]]:
        return {cache.config.name: cache.stats() for cache in self._caches}

    def front_hit_latency(self) -> int:
        if not self._caches:
            # Fallback to a reasonable default if no caches are configured
            return 4
        return self._caches[0].hit_latency

    def report_metrics(self) -> Dict[str, Any]:
        """Reports a consolidated dictionary of all memory-related metrics."""
        cache_metrics: Dict[str, Dict[str, float | int]] = {}
        for cache in self._caches:
            counters = cache.stats()
            total = counters["hits"] + counters["misses"]
            miss_rate = counters["misses"] / total if total else 0.0
            cache_metrics[cache.config.name] = {
                "hits": counters["hits"],
                "misses": counters["misses"],
                "miss_rate": miss_rate,
            }

        load_requests = self._stats["load_requests"]
        store_requests = self._stats["store_requests"]
        total_requests = load_requests + store_requests
        total_latency = self._stats["total_latency_cycles"]
        average_latency = total_latency / total_requests if total_requests else 0.0
        memory_access_metrics = {
            "load_requests": load_requests,
            "store_requests": store_requests,
            "total_requests": total_requests,
            "total_latency_cycles": total_latency,
            "average_latency_cycles": average_latency,
            "bus_transaction_latency_cycles": self._stats[
                "bus_transaction_latency_cycles"
            ],
            "dram_wait_cycles": self._stats["dram_latency_cycles"],
        }

        return {
            "memory_system": memory_access_metrics,
            "caches": cache_metrics,
            "bus": self.bus.metrics.snapshot(),
            "dram": self.dram.metrics.snapshot(),
        }

    def _reset_stats(self) -> None:
        self._stats = {
            "load_requests": 0,
            "store_requests": 0,
            "total_latency_cycles": 0,
            "bus_transaction_latency_cycles": 0,
            "dram_latency_cycles": 0,
        }

    def _record_access(
        self, *, access_type: str, start_time: int, done_at: int
    ) -> None:
        latency = max(0, done_at - start_time)
        self._stats["total_latency_cycles"] += latency
        if access_type == "read":
            self._stats["load_requests"] += 1
        else:
            self._stats["store_requests"] += 1

    def _resolve_start_time(self, request_time: Optional[int]) -> int:
        if request_time is None:
            return self._now
        if request_time < 0:
            raise ValueError("request_time cannot be negative")
        if request_time < self._now:
            raise ValueError("request_time cannot move time backwards")
        return request_time

    def _align_address(self, address: int, line_size: int) -> int:
        if address < 0:
            raise ValueError("Address must be non-negative")
        return (address // line_size) * line_size

    def _access_hierarchy(
        self,
        level_idx: int,
        *,
        address: int,
        request_time: int,
        access_type: str,
        master_id: int,
    ) -> int:
        if level_idx >= len(self._caches):
            return self._access_main_memory(
                address, request_time, master_id, access_type
            )

        cache = self._caches[level_idx]
        line_size = cache.line_size
        aligned_address = self._align_address(address, line_size)
        line, index = cache.lookup(aligned_address)
        ready_time = request_time + cache.hit_latency

        if line is not None:
            self.logger.debug(
                "memory.cache.hit",
                extra={
                    "level": cache.config.name,
                    "address": aligned_address,
                    "master_id": master_id,
                    "access_type": access_type,
                },
            )
            if access_type == "write":
                cache.mark_dirty(line)
            return ready_time

        self.logger.debug(
            "memory.cache.miss",
            extra={
                "level": cache.config.name,
                "address": aligned_address,
                "master_id": master_id,
                "access_type": access_type,
            },
        )
        lower_request_time = ready_time  # Pay this level's latency before descending.
        next_ready = self._access_hierarchy(
            level_idx + 1,
            address=aligned_address,
            request_time=lower_request_time,
            access_type="read",
            master_id=master_id,
        )
        new_line, eviction = cache.insert(index, aligned_address)
        if access_type == "write":
            cache.mark_dirty(new_line)

        fill_start = max(next_ready, lower_request_time)
        fill_complete = fill_start + cache.hit_latency

        if eviction and eviction.dirty and cache.config.write_back:
            self.logger.debug(
                "memory.cache.writeback",
                extra={
                    "level": cache.config.name,
                    "evict_address": eviction.address,
                    "master_id": master_id,
                },
            )
            writeback_done = self._access_hierarchy(
                level_idx + 1,
                address=eviction.address,
                request_time=fill_complete,
                access_type="write",
                master_id=master_id,
            )
            fill_complete = max(fill_complete, writeback_done)
        elif eviction:
            self.logger.debug(
                "memory.cache.eviction",
                extra={
                    "level": cache.config.name,
                    "evict_address": eviction.address,
                    "dirty": eviction.dirty,
                    "master_id": master_id,
                },
            )

        return fill_complete

    def _access_main_memory(
        self,
        address: int,
        request_time: int,
        master_id: int,
        _access_type: str,
    ) -> int:
        line_size = (
            self._caches[-1].line_size if self._caches else DEFAULT_L2_CONFIG.line_size
        )
        size = line_size
        self.bus.sync_time(request_time)
        _, bus_done = self.bus.request(
            master_id=master_id,
            bytes=size,
            request_at=request_time,
        )
        dram_done = self.dram.access(address, size, request_time=request_time)
        completion = max(bus_done, dram_done)
        self._stats["bus_transaction_latency_cycles"] += max(0, bus_done - request_time)
        self._stats["dram_latency_cycles"] += max(0, dram_done - request_time)
        self.logger.debug(
            "memory.main_memory",
            extra={
                "address": address,
                "size": size,
                "master_id": master_id,
                "request_time": request_time,
                "bus_done": bus_done,
                "dram_done": dram_done,
                "completion": completion,
            },
        )
        return completion

    def _process_range(
        self,
        *,
        address: int,
        size: int,
        request_time: Optional[int],
        access_type: str,
        master_id: int,
    ) -> int:
        if size <= 0:
            raise ValueError("size must be positive")

        start_time = self._resolve_start_time(request_time)
        done_at = start_time
        remaining = size
        current = address
        line_size = (
            self._caches[0].line_size if self._caches else DEFAULT_L1_CONFIG.line_size
        )

        while remaining > 0:
            offset = current % line_size
            chunk = min(line_size - offset, remaining)
            done_at = max(
                done_at,
                self._access_hierarchy(
                    0,
                    address=current,
                    request_time=done_at,
                    access_type=access_type,
                    master_id=master_id,
                ),
            )
            current += chunk
            remaining -= chunk

        self._now = max(self._now, done_at)
        self._record_access(
            access_type=access_type, start_time=start_time, done_at=done_at
        )
        return done_at

    def load(
        self,
        address: int,
        size: int,
        *,
        request_time: Optional[int] = None,
        master_id: int = 0,
    ) -> int:
        return self._process_range(
            address=address,
            size=size,
            request_time=request_time,
            access_type="read",
            master_id=master_id,
        )

    def store(
        self,
        address: int,
        size: int,
        *,
        request_time: Optional[int] = None,
        master_id: int = 0,
    ) -> int:
        return self._process_range(
            address=address,
            size=size,
            request_time=request_time,
            access_type="write",
            master_id=master_id,
        )
