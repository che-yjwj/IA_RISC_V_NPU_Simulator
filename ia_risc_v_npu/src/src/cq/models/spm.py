"""Scratchpad memory access contention model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass(slots=True)
class ScratchpadTimingModel:
    """Track bank/port availability for scratchpad accesses."""

    banks: int = 8
    bank_width_bytes: int = 64
    access_latency: int = 2
    conflict_penalty: int = 3
    port_count: int = 2
    _bank_ready: Dict[int, int] = field(default_factory=dict, init=False)
    _port_ready: list[int] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._bank_ready = {bank: 0 for bank in range(max(1, self.banks))}
        self._port_ready = [0 for _ in range(max(1, self.port_count))]

    def _banks_for_range(self, offset: int, size_bytes: int) -> Set[int]:
        if size_bytes <= 0:
            return set()
        step = max(1, self.bank_width_bytes)
        banks: Set[int] = set()
        limit = offset + size_bytes
        for cursor in range(offset, limit, step):
            bank = (cursor // step) % max(1, self.banks)
            banks.add(bank)
        # Ensure the tail byte is accounted for
        tail_bank = ((limit - 1) // step) % max(1, self.banks)
        banks.add(tail_bank)
        return banks

    def access(self, offset: int, size_bytes: int, *, at: int) -> int:
        """Return the cycle when the access completes."""

        touched = self._banks_for_range(offset, size_bytes)
        if not touched:
            return at

        # Ports serve requests in the order they become free.
        port_index = min(range(len(self._port_ready)), key=self._port_ready.__getitem__)
        start = max(at, self._port_ready[port_index])

        for bank in touched:
            start = max(start, self._bank_ready[bank])

        conflict_cycles = (len(touched) - 1) * self.conflict_penalty
        duration = self.access_latency + conflict_cycles
        done_at = start + duration

        self._port_ready[port_index] = done_at
        for bank in touched:
            self._bank_ready[bank] = done_at

        return done_at
