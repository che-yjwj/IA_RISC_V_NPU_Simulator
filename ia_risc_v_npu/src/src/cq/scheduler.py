"""Scheduling helpers for the CQ dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence

from .schema import CQCommand


class SchedulingPolicy(str, Enum):
    """Available scheduling policies for CQ execution."""

    FIFO = "fifo"
    ROUND_ROBIN = "rr"
    EARLIEST_DEADLINE_FIRST = "edf"


@dataclass(slots=True)
class SchedulingContext:
    """Mutable state shared across scheduling decisions."""

    tick: int = 0
    lane_usage: Dict[str, int] = field(default_factory=dict)


def lane_for_command(command: CQCommand) -> str:
    """Group commands into logical execution lanes."""

    opcode = (command.opcode or "").upper()
    if opcode.startswith("DMA"):
        return "dma"
    if opcode.startswith("TE_"):
        return "te"
    if opcode.startswith("FENCE"):
        return "fence"
    return "misc"


def _extract_deadline(command: CQCommand) -> Optional[int]:
    """Best-effort lookup for deadline metadata."""

    operands = command.operands or {}
    trace = command.trace or {}

    for key in ("deadline", "deadline_cycles", "deadline_at"):
        raw = operands.get(key) or trace.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


class _BaseStrategy:
    """Common behaviour for scheduling strategies."""

    policy: SchedulingPolicy

    def __init__(self, policy: SchedulingPolicy) -> None:
        self.policy = policy

    def select(
        self,
        ready: Sequence[CQCommand],
        *,
        context: SchedulingContext,
        queued_order: Dict[str, int],
    ) -> CQCommand:
        raise NotImplementedError


class _FIFOStrategy(_BaseStrategy):
    def __init__(self) -> None:
        super().__init__(SchedulingPolicy.FIFO)

    def select(
        self,
        ready: Sequence[CQCommand],
        *,
        context: SchedulingContext,
        queued_order: Dict[str, int],
    ) -> CQCommand:
        if not ready:
            raise ValueError("No commands ready for FIFO scheduling")
        return ready[0]


class _RoundRobinStrategy(_BaseStrategy):
    def __init__(self) -> None:
        super().__init__(SchedulingPolicy.ROUND_ROBIN)
        self._last_lane_index = -1
        self._lane_sequence: List[str] = []

    def select(
        self,
        ready: Sequence[CQCommand],
        *,
        context: SchedulingContext,
        queued_order: Dict[str, int],
    ) -> CQCommand:
        if not ready:
            raise ValueError("No commands ready for RR scheduling")

        lane_map: Dict[str, List[CQCommand]] = {}
        lane_order: List[str] = []

        for command in ready:
            lane = lane_for_command(command)
            lane_map.setdefault(lane, []).append(command)
            if lane not in lane_order:
                lane_order.append(lane)

        if not lane_order:
            return ready[0]

        if lane_order != self._lane_sequence:
            self._lane_sequence = lane_order
            self._last_lane_index = -1

        next_lane_index = (self._last_lane_index + 1) % len(self._lane_sequence)
        self._last_lane_index = next_lane_index
        chosen_lane = self._lane_sequence[next_lane_index]
        selections = lane_map.get(chosen_lane)
        if not selections:
            # Fallback: pick the earliest queued command if lane depleted.
            ordered = sorted(
                ready, key=lambda cmd: queued_order.get(cmd.cmd_id, float("inf"))
            )
            return ordered[0]
        return selections[0]


class _EDFStrategy(_BaseStrategy):
    def __init__(self) -> None:
        super().__init__(SchedulingPolicy.EARLIEST_DEADLINE_FIRST)

    def select(
        self,
        ready: Sequence[CQCommand],
        *,
        context: SchedulingContext,
        queued_order: Dict[str, int],
    ) -> CQCommand:
        if not ready:
            raise ValueError("No commands ready for EDF scheduling")

        def sort_key(command: CQCommand) -> tuple[int, int]:
            deadline = _extract_deadline(command)
            deadline_value = deadline if deadline is not None else float("inf")
            return (deadline_value, queued_order.get(command.cmd_id, float("inf")))

        ordered = sorted(ready, key=sort_key)
        return ordered[0]


def build_strategy(policy: SchedulingPolicy) -> _BaseStrategy:
    if policy is SchedulingPolicy.FIFO:
        return _FIFOStrategy()
    if policy is SchedulingPolicy.ROUND_ROBIN:
        return _RoundRobinStrategy()
    if policy is SchedulingPolicy.EARLIEST_DEADLINE_FIRST:
        return _EDFStrategy()
    raise ValueError(f"Unsupported scheduling policy: {policy!r}")


__all__ = [
    "SchedulingPolicy",
    "SchedulingContext",
    "lane_for_command",
    "build_strategy",
]
