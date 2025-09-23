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
        if row_hit:
            latency = self.config.t_cas
        else:
            latency = self.config.t_rp + self.config.t_rcd + self.config.t_cas

        done_at = ready_at + latency
        self.bank_free_at[bank] = done_at
        self.row_open[bank] = row
        self._now = max(self._now, done_at)
        return done_at


class MemorySystem:
    """Container for timing-aware memory components."""

    def __init__(self, dram_config: Optional[DRAMConfig] = None):
        self.dram = DRAM(dram_config)

    def access_dram(self, address: int, size: int, *, request_time: Optional[int] = None) -> int:
        return self.dram.access(address, size, request_time=request_time)

    def map_address(self, address: int) -> Tuple[int, int]:
        return self.dram.map_address(address)
