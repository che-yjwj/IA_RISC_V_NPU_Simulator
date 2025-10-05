from __future__ import annotations

import logging
import math
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from src.simulator.models import BusMetrics, BusRequest

LOGGER = logging.getLogger(__name__)


class SPM:
    """Scratchpad Memory (SPM)"""

    def __init__(self, size_kb: int):
        self.size = size_kb * 1024
        self.memory = bytearray(self.size)

    def read(self, address: int, size: int) -> bytes:
        if not (0 <= address < self.size and 0 <= address + size <= self.size):
            raise IndexError(
                f"SPM read out of bounds: address={address}, size={size}, "
                f"SPM size={self.size}"
            )
        return self.memory[address : address + size]

    def write(self, address: int, data: bytes) -> None:
        if not (0 <= address < self.size and 0 <= address + len(data) <= self.size):
            raise IndexError(
                f"SPM write out of bounds: address={address}, data_len={len(data)}, "
                f"SPM size={self.size}"
            )
        self.memory[address : address + len(data)] = data


class Bus:
    """Deterministic bus model with slice-aware bandwidth scheduling."""

    def __init__(
        self,
        *,
        slice_bytes: int = 32,
        bandwidth_bytes_per_cycle: int = 16,
        grant_latency: int = 1,
        metrics: Optional[BusMetrics] = None,
        logger: Optional[logging.Logger] = None,
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
        self.logger = logger or LOGGER

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

    def add_device(
        self, name: str, device: object, start_addr: int, end_addr: int
    ) -> None:
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

        if isinstance(master_id, int):
            master_id_int = master_id
        elif hasattr(master_id, "value") and isinstance(master_id.value, int):
            master_id_int = int(master_id)
        else:
            raise TypeError("master_id must be an integer or IntEnum-like object")

        queue = self._queues.setdefault(master_id_int, deque())
        if master_id_int not in self._masters_order:
            self._masters_order.append(master_id_int)

        request = BusRequest(
            master_id=master_id_int, size_bytes=bytes, request_at=request_at
        )
        queue.append(request)
        self._pending_requests += 1
        self.metrics.on_request(len(self._active_requests) + self._pending_requests)

        self.logger.debug(
            "bus.request.queued",
            extra={
                "master_id": master_id_int,
                "size_bytes": bytes,
                "request_at": request_at,
                "pending": self._pending_requests,
                "active": len(self._active_requests),
            },
        )

        self._schedule()

        self._now = max(self._now, request_at)

        self._active_requests.append(request)

        if request.grant_at is None or request.done_at is None:
            raise RuntimeError(
                "Bus scheduling did not produce a grant and completion time."
            )

        self.logger.debug(
            "bus.request.scheduled",
            extra={
                "master_id": master_id_int,
                "request_at": request.request_at,
                "grant_at": request.grant_at,
                "start_at": request.start_at,
                "done_at": request.done_at,
                "transfer_cycles": request.transfer_cycles,
            },
        )

        return request.grant_at, request.done_at

    def completed_requests(self) -> Tuple[BusRequest, ...]:
        return tuple(self._completed_requests)

    def sync_time(self, now: int) -> None:
        if now < 0:
            raise ValueError("now cannot be negative.")
        if now < self._now:
            raise ValueError("Simulation time cannot move backwards.")
        self.logger.debug(
            "bus.sync_time",
            extra={
                "sync_to": now,
                "previous": self._now,
                "active": len(self._active_requests),
                "pending": self._pending_requests,
            },
        )
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
        self._active_requests = [
            req
            for req in self._active_requests
            if req.done_at is None or req.done_at > now
        ]

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
        arrival_times = [
            queue[0].request_at for queue in self._queues.values() if queue
        ]
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

            self.logger.debug(
                "bus.schedule.grant",
                extra={
                    "master_id": master_id,
                    "request_at": request.request_at,
                    "grant_at": grant_event_time,
                    "start_at": start_time,
                    "done_at": done_at,
                    "queue_depth": len(queue),
                    "pending": self._pending_requests,
                },
            )

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

        self.logger.debug(
            "bus.schedule.idle",
            extra={
                "available_at": self._available_at,
                "pending": self._pending_requests,
                "active": len(self._active_requests),
            },
        )

    def _calculate_transfer_cycles(self, size_bytes: int) -> int:
        if size_bytes <= 0:
            return 0

        full_slices, remainder = divmod(size_bytes, self.slice_bytes)
        slice_cycles = math.ceil(self.slice_bytes / self.bandwidth_bytes_per_cycle)
        total_cycles = full_slices * slice_cycles
        if remainder:
            total_cycles += math.ceil(remainder / self.bandwidth_bytes_per_cycle)
        return total_cycles

    def _find_device(
        self, address: int, size: int
    ) -> Tuple[Optional[object], Optional[int]]:
        self.logger.debug(
            "bus.lookup",
            extra={"address": address, "size": size},
        )
        for name, info in self.devices.items():
            start = info["start_addr"]
            end = info["end_addr"]
            self.logger.debug(
                "bus.lookup.check",
                extra={"device": name, "start": start, "end": end},
            )
            if start <= address and address + size - 1 <= end:
                self.logger.debug(
                    "bus.lookup.hit",
                    extra={"device": name, "address": address, "size": size},
                )
                return info["device"], address - start
        self.logger.debug(
            "bus.lookup.miss",
            extra={"address": address, "size": size},
        )
        return None, None

    def read(self, address: int, size: int) -> bytes:
        device, local_addr = self._find_device(address, size)
        if device:
            if hasattr(device, "read"):
                return device.read(local_addr, size)  # type: ignore[no-any-return]
            return device[local_addr : local_addr + size]  # type: ignore[index]
        raise MemoryError(
            f"No device found or access out of bounds for address {address} "
            f"with size {size}"
        )

    def write(self, address: int, data: bytes) -> None:
        device, local_addr = self._find_device(address, len(data))
        if not device:
            raise MemoryError(
                f"No device found or access out of bounds for address {address} "
                f"with size {len(data)}"
            )

        if hasattr(device, "write"):
            device.write(local_addr, data)
        else:
            device[local_addr : local_addr + len(data)] = data  # type: ignore[index]
