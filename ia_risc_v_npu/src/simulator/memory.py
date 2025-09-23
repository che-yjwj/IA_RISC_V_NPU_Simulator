from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple


LOGGER = logging.getLogger(__name__)


class SPM:
    """Scratchpad Memory (SPM)"""

    def __init__(self, size_kb: int):
        self.size = size_kb * 1024
        self.memory = bytearray(self.size)

    def read(self, address: int, size: int) -> bytes:
        if not (0 <= address < self.size and 0 <= address + size <= self.size):
            raise IndexError(
                f"SPM read out of bounds: address={address}, size={size}, SPM size={self.size}"
            )
        return self.memory[address : address + size]

    def write(self, address: int, data: bytes) -> None:
        if not (0 <= address < self.size and 0 <= address + len(data) <= self.size):
            raise IndexError(
                f"SPM write out of bounds: address={address}, data_len={len(data)}, SPM size={self.size}"
            )
        self.memory[address : address + len(data)] = data


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

    def on_grant(self, *, wait_cycles: int, grant_latency: int, transfer_cycles: int) -> None:
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
            raise ValueError("Cache size must be divisible by line_size * associativity")


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


class CacheLevel:
    """Set-associative cache metadata with LRU replacement."""

    def __init__(self, config: CacheConfig) -> None:
        self.config = config
        self.num_sets = self.config.size_bytes // (self.config.line_size * self.config.associativity)
        if self.num_sets <= 0:
            raise ValueError("Derived number of sets must be positive")

        self.sets: List[List[CacheLine]] = [
            [CacheLine() for _ in range(self.config.associativity)] for _ in range(self.num_sets)
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

    def insert(self, index: int, address: int) -> Tuple[CacheLine, Optional[CacheEviction]]:
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

class Bus:
    """Deterministic bus model with slice-aware bandwidth scheduling."""

    def __init__(
        self,
        *,
        slice_bytes: int = 32,
        bandwidth_bytes_per_cycle: int = 16,
        grant_latency: int = 1,
        metrics: Optional[BusMetrics] = None,
    ) -> None:
        if slice_bytes <= 0:
            raise ValueError("slice_bytes must be greater than zero.")
        if bandwidth_bytes_per_cycle <= 0:
            raise ValueError("bandwidth_bytes_per_cycle must be greater than zero.")
        if grant_latency < 0:
            raise ValueError("grant_latency cannot be negative.")

        self.slice_bytes = slice_bytes
        self.bandwidth_bytes_per_cycle = bandwidth_bytes_per_cycle
        self.grant_latency = grant_latency
        self.metrics = metrics or BusMetrics()

        self.devices: Dict[str, Dict[str, object]] = {}

        self._queues: Dict[int, Deque[BusRequest]] = {}
        self._masters_order: List[int] = []
        self._rr_index: int = -1
        self._available_at: int = 0
        self._pending_requests: int = 0
        self._completed_requests: List[BusRequest] = []
        self._active_requests: List[BusRequest] = []
        self._now: int = 0

    @property
    def now(self) -> int:
        """Return the last simulation time observed by the bus."""

        return self._now

    def add_device(self, name: str, device: object, start_addr: int, end_addr: int) -> None:
        self.devices[name] = {
            "device": device,
            "start_addr": start_addr,
            "end_addr": end_addr,
        }

    def request(
        self,
        master_id: int,
        bytes: int,
        *,
        request_at: Optional[int] = None,
    ) -> Tuple[int, int]:
        if bytes <= 0:
            raise ValueError("bytes must be greater than zero.")

        request_at = self._resolve_request_time(request_at)
        self._evict_completed(request_at)

        queue = self._queues.setdefault(master_id, deque())
        if master_id not in self._masters_order:
            self._masters_order.append(master_id)

        request = BusRequest(master_id=master_id, size_bytes=bytes, request_at=request_at)
        queue.append(request)
        self._pending_requests += 1
        self.metrics.on_request(len(self._active_requests) + self._pending_requests)

        self._schedule()

        self._now = max(self._now, request_at)

        self._active_requests.append(request)

        if request.grant_at is None or request.done_at is None:
            raise RuntimeError("Bus scheduling did not produce a grant and completion time.")

        return request.grant_at, request.done_at

    def completed_requests(self) -> Tuple[BusRequest, ...]:
        return tuple(self._completed_requests)

    def sync_time(self, now: int) -> None:
        if now < 0:
            raise ValueError("now cannot be negative.")
        if now < self._now:
            raise ValueError("Simulation time cannot move backwards.")
        self._now = now
        self._evict_completed(now)

    def _resolve_request_time(self, request_at: Optional[int]) -> int:
        if request_at is None:
            return self._now
        if request_at < 0:
            raise ValueError("request_at cannot be negative.")
        if request_at < self._now:
            raise ValueError("request_at cannot be earlier than the current time.")
        return request_at

    def _evict_completed(self, now: int) -> None:
        if not self._active_requests:
            return
        self._active_requests = [req for req in self._active_requests if req.done_at is None or req.done_at > now]

    def _select_next_master(self, available_at: int) -> Optional[int]:
        if not self._masters_order:
            return None

        total = len(self._masters_order)
        for offset in range(1, total + 1):
            idx = (self._rr_index + offset) % total
            master_id = self._masters_order[idx]
            queue = self._queues.get(master_id)
            if not queue:
                continue
            head = queue[0]
            if head.request_at <= available_at:
                self._rr_index = idx
                return master_id
        return None

    def _next_arrival_time(self) -> Optional[int]:
        arrival_times = [queue[0].request_at for queue in self._queues.values() if queue]
        if not arrival_times:
            return None
        return min(arrival_times)

    def _schedule(self) -> None:
        while self._pending_requests > 0:
            master_id = self._select_next_master(self._available_at)
            if master_id is None:
                next_arrival = self._next_arrival_time()
                if next_arrival is None:
                    return
                self._available_at = max(self._available_at, next_arrival)
                continue

            queue = self._queues.get(master_id)
            if not queue:
                continue

            request = queue[0]
            grant_event_time = max(self._available_at, request.request_at)
            start_time = grant_event_time + self.grant_latency
            transfer_cycles = self._calculate_transfer_cycles(request.size_bytes)
            done_at = start_time + transfer_cycles

            request.grant_at = grant_event_time
            request.start_at = start_time
            request.done_at = done_at
            request.transfer_cycles = transfer_cycles

            queue.popleft()

            self._pending_requests -= 1
            wait_cycles = grant_event_time - request.request_at
            self.metrics.on_grant(
                wait_cycles=wait_cycles,
                grant_latency=self.grant_latency,
                transfer_cycles=transfer_cycles,
            )

            self._available_at = done_at
            self._completed_requests.append(request)

    def _calculate_transfer_cycles(self, size_bytes: int) -> int:
        if size_bytes <= 0:
            return 0

        full_slices, remainder = divmod(size_bytes, self.slice_bytes)
        slice_cycles = math.ceil(self.slice_bytes / self.bandwidth_bytes_per_cycle)
        total_cycles = full_slices * slice_cycles
        if remainder:
            total_cycles += math.ceil(remainder / self.bandwidth_bytes_per_cycle)
        return total_cycles

    def _find_device(self, address: int, size: int) -> Tuple[Optional[object], Optional[int]]:
        LOGGER.debug("bus lookup: address=%s size=%s", address, size)
        for name, info in self.devices.items():
            start = info["start_addr"]
            end = info["end_addr"]
            LOGGER.debug("  checking %s: start=%s end=%s", name, start, end)
            if start <= address and address + size - 1 <= end:
                LOGGER.debug("  device %s selected", name)
                return info["device"], address - start
        LOGGER.debug("  no device for address=%s size=%s", address, size)
        return None, None

    def read(self, address: int, size: int) -> bytes:
        device, local_addr = self._find_device(address, size)
        if device:
            if hasattr(device, "read"):
                return device.read(local_addr, size)  # type: ignore[no-any-return]
            return device[local_addr : local_addr + size]  # type: ignore[index]
        raise MemoryError(
            f"No device found or access out of bounds for address {address} with size {size}"
        )

    def write(self, address: int, data: bytes) -> None:
        device, local_addr = self._find_device(address, len(data))
        if not device:
            raise MemoryError(
                f"No device found or access out of bounds for address {address} with size {len(data)}"
            )

        if hasattr(device, "write"):
            device.write(local_addr, data)
        else:
            device[local_addr : local_addr + len(data)] = data  # type: ignore[index]


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


class DRAM:
    """Simple DRAM timing approximation with bank/row tracking."""

    def __init__(self, config: Optional[DRAMConfig] = None):
        self.config = config or DRAMConfig()
        self.bank_free_at: List[int] = [0] * self.config.banks
        self.row_open: List[Optional[int]] = [None] * self.config.banks
        self._now = 0

    def reset(self) -> None:
        self.bank_free_at = [0] * self.config.banks
        self.row_open = [None] * self.config.banks
        self._now = 0

    def map_address(self, address: int) -> Tuple[int, int]:
        if address < 0:
            raise ValueError("Address must be non-negative")
        line_index = address // max(1, self.config.line_size)
        bank = line_index % self.config.banks
        row = address // self.config.row_size
        return bank, row

    def access(self, address: int, size: int, *, request_time: Optional[int] = None) -> int:
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
        self.bank_free_at[bank] = done_at
        self.row_open[bank] = row
        self._now = max(self._now, done_at)
        return done_at


DEFAULT_L1_CONFIG = CacheConfig(
    name="L1",
    size_bytes=32 * 1024,
    line_size=64,
    associativity=4,
    hit_latency=4,
)

DEFAULT_L2_CONFIG = CacheConfig(
    name="L2",
    size_bytes=256 * 1024,
    line_size=64,
    associativity=8,
    hit_latency=12,
)


class MemorySystem:
    """Deterministic cache hierarchy with bus/DRAM backing."""

    def __init__(
        self,
        bus: Bus,
        *,
        dram_config: Optional[DRAMConfig] = None,
        l1_config: Optional[CacheConfig] = None,
        l2_config: Optional[CacheConfig] = None,
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

    def reset(self) -> None:
        self.dram.reset()
        for cache in self._caches:
            cache.reset()
        self._now = 0

    def cache_stats(self) -> Dict[str, Dict[str, int]]:
        return {cache.config.name: cache.stats() for cache in self._caches}

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
            return self._access_main_memory(address, request_time, master_id, access_type)

        cache = self._caches[level_idx]
        line_size = cache.line_size
        aligned_address = self._align_address(address, line_size)
        line, index = cache.lookup(aligned_address)
        ready_time = request_time + cache.hit_latency

        if line is not None:
            if access_type == "write":
                cache.mark_dirty(line)
            return ready_time

        next_ready = self._access_hierarchy(
            level_idx + 1,
            address=aligned_address,
            request_time=request_time,
            access_type="read",
            master_id=master_id,
        )
        new_line, eviction = cache.insert(index, aligned_address)
        if access_type == "write":
            cache.mark_dirty(new_line)

        fill_complete = max(next_ready, request_time) + cache.hit_latency

        if eviction and eviction.dirty and cache.config.write_back:
            writeback_done = self._access_hierarchy(
                level_idx + 1,
                address=eviction.address,
                request_time=fill_complete,
                access_type="write",
                master_id=master_id,
            )
            fill_complete = max(fill_complete, writeback_done)

        return fill_complete

    def _access_main_memory(
        self,
        address: int,
        request_time: int,
        master_id: int,
        _access_type: str,
    ) -> int:
        line_size = self._caches[-1].line_size if self._caches else DEFAULT_L2_CONFIG.line_size
        size = line_size
        self.bus.sync_time(request_time)
        _, bus_done = self.bus.request(
            master_id=master_id,
            bytes=size,
            request_at=request_time,
        )
        dram_done = self.dram.access(address, size, request_time=request_time)
        return max(bus_done, dram_done)

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
        line_size = self._caches[0].line_size if self._caches else DEFAULT_L1_CONFIG.line_size

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
