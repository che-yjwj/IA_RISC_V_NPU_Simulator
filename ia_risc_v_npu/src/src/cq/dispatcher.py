"""CQ dispatcher skeleton for AdaptiveSimulator integration.

This module is intentionally minimal: it only wires the command queue into
structural hooks so that subsequent stages can focus on timing/resource models
without reworking call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .schema import CommandQueue, CQCommand


@dataclass(slots=True)
class DispatchStats:
    """Aggregate metrics calculated from the dispatcher run."""

    average_queue_wait: float = 0.0
    max_queue_wait: int = 0
    total_queue_wait: int = 0
    commands_with_zero_wait: int = 0


@dataclass(slots=True)
class DispatchTrace:
    """Lightweight trace metadata collected during CQ execution."""

    queued: List[str] = field(default_factory=list)
    scheduled: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    state_history: Dict[str, list[str]] = field(default_factory=dict)
    trace_metadata: Dict[str, Dict[str, object]] = field(default_factory=dict)
    timestamps: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def _record_state(
        self,
        command: CQCommand,
        state: str,
        *,
        reason: Optional[str] = None,
        tick: int,
    ) -> None:
        entry = state if reason is None else f"{state}:{reason}"
        history = self.state_history.setdefault(command.cmd_id, [])
        history.append(entry)
        if command.trace and command.cmd_id not in self.trace_metadata:
            self.trace_metadata[command.cmd_id] = dict(command.trace)
        self.timestamps.setdefault(command.cmd_id, {})[state] = tick

    def record_queued(self, command: CQCommand, *, tick: int) -> None:
        self.queued.append(command.cmd_id)
        self._record_state(command, "queued", tick=tick)

    def record_schedule(self, command: CQCommand, *, tick: int) -> None:
        self.scheduled.append(command.cmd_id)
        self._record_state(command, "scheduled", tick=tick)

    def record_completion(self, command: CQCommand, *, tick: int) -> None:
        self.completed.append(command.cmd_id)
        self._record_state(command, "completed", tick=tick)

    def record_rejection(self, command: CQCommand, reason: str, *, tick: int) -> None:
        self.rejected.append(f"{command.cmd_id}:{reason}")
        self._record_state(command, "rejected", reason=reason, tick=tick)

    def states(self, cmd_id: str) -> tuple[str, ...]:
        return tuple(self.state_history.get(cmd_id, []))

    def trace_ids(self, cmd_id: str) -> Dict[str, object]:
        return self.trace_metadata.get(cmd_id, {})


@dataclass(slots=True)
class DispatchOutcome:
    """Result snapshot produced by the dispatcher runtime."""

    commands_executed: int
    trace: DispatchTrace
    stats: DispatchStats


class CQDispatcher:
    """Simple FIFO dispatcher for CQ commands.

    The current implementation is a stub that validates ordering and records
    basic execution markers.  Future iterations will translate each command
    into bus/NPU operations and integrate with the simulator event scheduler.
    """

    def __init__(self, *, trace: Optional[DispatchTrace] = None) -> None:
        self.trace = trace or DispatchTrace()

    def run(self, queue: CommandQueue) -> DispatchOutcome:
        remaining_deps = {
            command.cmd_id: set(command.dependencies) for command in queue
        }
        executed = 0
        queue_wait_ticks: list[int] = []
        tick = 0

        for command in queue:
            self.trace.record_queued(command, tick=tick)
            tick += 1
            unmet = remaining_deps[command.cmd_id]
            if unmet:
                self.trace.record_rejection(
                    command,
                    reason=f"dependencies not satisfied: {', '.join(sorted(unmet))}",
                    tick=tick,
                )
                tick += 1
                continue

            self.trace.record_schedule(command, tick=tick)
            queued_tick = self.trace.timestamps[command.cmd_id]["queued"]
            queue_wait = tick - queued_tick
            queue_wait_ticks.append(queue_wait)
            tick += 1
            # TODO: integrate with simulator subsystems (DMA, TE, etc.).
            self.trace.record_completion(command, tick=tick)
            executed += 1
            tick += 1

            for dependents in remaining_deps.values():
                dependents.discard(command.cmd_id)

        stats = self._build_stats(queue_wait_ticks)
        return DispatchOutcome(
            commands_executed=executed, trace=self.trace, stats=stats
        )

    @staticmethod
    def _build_stats(queue_wait_ticks: List[int]) -> DispatchStats:
        if not queue_wait_ticks:
            return DispatchStats()
        total = sum(queue_wait_ticks)
        max_wait = max(queue_wait_ticks)
        zero_wait = sum(1 for value in queue_wait_ticks if value == 0)
        average = total / len(queue_wait_ticks)
        return DispatchStats(
            average_queue_wait=average,
            max_queue_wait=max_wait,
            total_queue_wait=total,
            commands_with_zero_wait=zero_wait,
        )


def replay_dependencies(commands: Iterable[CQCommand]) -> dict[str, list[str]]:
    """Return a map of command ids to the dependencies that remain unresolved.

    Useful for debugging and, eventually, for more advanced scheduling policies.
    """

    outstanding: dict[str, list[str]] = {}
    completed: set[str] = set()
    for command in commands:
        unmet = [dep for dep in command.dependencies if dep not in completed]
        if unmet:
            outstanding[command.cmd_id] = unmet
        else:
            completed.add(command.cmd_id)
    return outstanding


__all__ = [
    "CQDispatcher",
    "DispatchOutcome",
    "DispatchTrace",
    "DispatchStats",
    "replay_dependencies",
]
