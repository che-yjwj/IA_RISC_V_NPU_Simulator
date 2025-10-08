"""CQ dispatcher skeleton for AdaptiveSimulator integration.

This module is intentionally minimal: it only wires the command queue into
structural hooks so that subsequent stages can focus on timing/resource models
without reworking call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Set

from .scheduler import (
    SchedulingContext,
    SchedulingPolicy,
    build_strategy,
    lane_for_command,
)
from .schema import CommandQueue, CQCommand


class CQDeadlockError(RuntimeError):
    """Raised when a dependency cycle prevents CQ execution."""


def _assert_acyclic(queue: CommandQueue) -> None:
    graph = {command.cmd_id: tuple(command.dependencies) for command in queue}
    visited: set[str] = set()

    for start in graph:
        if start in visited:
            continue

        stack: list[tuple[str, bool]] = [(start, False)]
        active: set[str] = set()
        path: list[str] = []
        path_index: dict[str, int] = {}

        while stack:
            node, expanded = stack.pop()

            if expanded:
                active.remove(node)
                path_index.pop(node)
                path.pop()
                visited.add(node)
                continue

            if node in visited:
                continue

            if node in active:
                idx = path_index[node]
                cycle_path = path[idx:] + [node]
                raise CQDeadlockError(
                    "Detected dependency cycle: " + "->".join(cycle_path)
                )

            stack.append((node, True))
            active.add(node)
            path_index[node] = len(path)
            path.append(node)

            for dep in reversed(graph.get(node, ())):
                if dep not in graph:
                    continue
                if dep in active:
                    idx = path_index[dep]
                    cycle_path = path[idx:] + [dep]
                    raise CQDeadlockError(
                        "Detected dependency cycle: " + "->".join(cycle_path)
                    )
                if dep not in visited:
                    stack.append((dep, False))


_DEFAULT_LANE_LIMITS: Dict[str, int] = {
    "dma": 1,
    "te": 1,
    "fence": 1,
    "misc": 1,
}


@dataclass(slots=True)
class DispatchStats:
    """Aggregate metrics calculated from the dispatcher run."""

    average_queue_wait: float = 0.0
    max_queue_wait: int = 0
    total_queue_wait: int = 0
    commands_with_zero_wait: int = 0
    lane_totals: Dict[str, int] = field(default_factory=dict)
    lane_max_concurrency: Dict[str, int] = field(default_factory=dict)


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
    """CQ dispatcher with pluggable scheduling policies.

    The runtime validates dependency graphs, records queue statistics, and invokes
    the provided executor callback.  Future iterations will translate each command
    into bus/NPU operations and integrate with the simulator event scheduler.
    """

    def __init__(
        self,
        *,
        trace: Optional[DispatchTrace] = None,
        clock: Optional[Callable[[], int]] = None,
        policy: SchedulingPolicy = SchedulingPolicy.FIFO,
        lane_limits: Optional[Mapping[str, int]] = None,
    ) -> None:
        self.trace = trace or DispatchTrace()
        self._clock = clock
        self.policy = policy
        self._lane_limits = self._normalise_lane_limits(lane_limits)

    def run(
        self,
        queue: CommandQueue,
        *,
        executor: Optional[Callable[[CQCommand], bool]] = None,
    ) -> DispatchOutcome:
        commands = list(queue)
        if not commands:
            return DispatchOutcome(
                commands_executed=0, trace=self.trace, stats=DispatchStats()
            )

        _assert_acyclic(queue)
        strategy = build_strategy(self.policy)
        context = SchedulingContext()

        queue_wait_ticks: list[int] = []
        tick = 0
        queued_order: Dict[str, int] = {}
        pending_ids: Set[str] = set()
        executed_ids: Set[str] = set()
        rejected_ids: Set[str] = set()
        failure_ids: Set[str] = set()
        lane_totals: Dict[str, int] = {}
        lane_max_concurrency: Dict[str, int] = {}
        for index, command in enumerate(commands):
            queued_tick = self._now(tick)
            self.trace.record_queued(command, tick=queued_tick)
            queued_order[command.cmd_id] = index
            pending_ids.add(command.cmd_id)
            if self._clock is None:
                tick += 1

        if self._clock is None:
            tick = 0

        while pending_ids:
            ready: list[CQCommand] = [
                command
                for command in commands
                if command.cmd_id in pending_ids
                and set(command.dependencies or ()).issubset(executed_ids)
            ]
            if not ready:
                unschedulable = [
                    command
                    for command in commands
                    if command.cmd_id in pending_ids and command.cmd_id not in rejected_ids
                ]
                if not unschedulable:
                    break
                for command in unschedulable:
                    reason = self._resolve_rejection_reason(
                        command,
                        executed_ids=executed_ids,
                        failure_ids=failure_ids,
                    )
                    self.trace.record_rejection(
                        command,
                        reason=reason,
                        tick=self._now(tick),
                    )
                    rejected_ids.add(command.cmd_id)
                    pending_ids.remove(command.cmd_id)
                continue

            context.tick = tick
            context.lane_usage.clear()
            scheduled_batch: list[CQCommand] = []
            remaining_ready: list[CQCommand] = list(ready)

            while remaining_ready:
                lane_filtered = [
                    command
                    for command in remaining_ready
                    if self._lane_has_capacity(command, context=context)
                ]
                if not lane_filtered:
                    break
                selected = strategy.select(
                    lane_filtered,
                    context=context,
                    queued_order=queued_order,
                )
                scheduled_batch.append(selected)
                lane = lane_for_command(selected)
                context.lane_usage[lane] = context.lane_usage.get(lane, 0) + 1
                remaining_ready = [
                    command
                    for command in remaining_ready
                    if command.cmd_id != selected.cmd_id
                ]

            if not scheduled_batch:
                selected = strategy.select(
                    ready,
                    context=context,
                    queued_order=queued_order,
                )
                scheduled_batch = [selected]
                lane = lane_for_command(selected)
                context.lane_usage[lane] = context.lane_usage.get(lane, 0) + 1

            batch_lane_counts: Dict[str, int] = {}
            for selected in scheduled_batch:
                lane = lane_for_command(selected)
                batch_lane_counts[lane] = batch_lane_counts.get(lane, 0) + 1
                lane_totals[lane] = lane_totals.get(lane, 0) + 1
            for lane, count in batch_lane_counts.items():
                if count > lane_max_concurrency.get(lane, 0):
                    lane_max_concurrency[lane] = count

            schedule_tick_base = self._now(tick)
            for selected in scheduled_batch:
                queued_tick = self.trace.timestamps[selected.cmd_id]["queued"]
                schedule_tick = max(schedule_tick_base, queued_tick)
                self.trace.record_schedule(selected, tick=schedule_tick)
                queue_wait = schedule_tick - queued_tick
                queue_wait_ticks.append(queue_wait)
            if self._clock is None:
                tick += 1

            for selected in scheduled_batch:
                success = True
                failure_logged = False
                if executor is not None:
                    try:
                        success = bool(executor(selected))
                    except Exception as exc:  # pragma: no cover - defensive guard
                        success = False
                        self.trace.record_rejection(
                            selected,
                            reason=f"execution_failed: {exc}",
                            tick=self._now(tick),
                        )
                        failure_logged = True

                if not success:
                    if executor is not None and not failure_logged:
                        self.trace.record_rejection(
                            selected,
                            reason="execution_failed",
                            tick=self._now(tick),
                        )
                    failure_ids.add(selected.cmd_id)
                    pending_ids.discard(selected.cmd_id)
                    rejected_ids.add(selected.cmd_id)
                    continue

                completion_tick = max(
                    self._now(tick),
                    self.trace.timestamps[selected.cmd_id].get("scheduled", 0),
                )
                self.trace.record_completion(selected, tick=completion_tick)
                executed_ids.add(selected.cmd_id)
                pending_ids.discard(selected.cmd_id)

        stats = self._build_stats(
            queue_wait_ticks,
            lane_totals=lane_totals,
            lane_max_concurrency=lane_max_concurrency,
        )
        return DispatchOutcome(
            commands_executed=len(executed_ids), trace=self.trace, stats=stats
        )

    def _now(self, fallback: int) -> int:
        if self._clock is not None:
            return int(self._clock())
        return fallback

    @staticmethod
    def _normalise_lane_limits(
        lane_limits: Optional[Mapping[str, int]],
    ) -> Dict[str, int]:
        limits = dict(_DEFAULT_LANE_LIMITS)
        if lane_limits is None:
            return limits
        for lane, value in lane_limits.items():
            lane_key = str(lane).strip().lower()
            if not lane_key:
                raise ValueError("lane name must be a non-empty string")
            try:
                capacity = int(value)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
                raise ValueError(
                    f"lane limit for '{lane}' must be an integer"
                ) from exc
            if capacity < 1:
                raise ValueError(
                    f"lane limit for '{lane}' must be >= 1 (got {capacity})"
                )
            limits[lane_key] = capacity
        return limits

    def _lane_capacity(self, lane: str) -> int:
        lane_key = lane.lower()
        if lane_key in self._lane_limits:
            return self._lane_limits[lane_key]
        return self._lane_limits.get("misc", 1)

    def _lane_has_capacity(
        self,
        command: CQCommand,
        *,
        context: SchedulingContext,
    ) -> bool:
        lane = lane_for_command(command)
        capacity = self._lane_capacity(lane)
        usage = context.lane_usage.get(lane, 0)
        return usage < capacity

    @staticmethod
    def _resolve_rejection_reason(
        command: CQCommand,
        *,
        executed_ids: Set[str],
        failure_ids: Set[str],
    ) -> str:
        unmet = sorted(set(command.dependencies or ()) - executed_ids)
        if unmet:
            return f"dependencies not satisfied: {', '.join(unmet)}"
        if command.dependencies:
            return "dependencies_unresolved"
        if command.cmd_id in failure_ids:
            return "execution_failed"
        return "unschedulable"

    @staticmethod
    def _build_stats(
        queue_wait_ticks: List[int],
        *,
        lane_totals: Dict[str, int],
        lane_max_concurrency: Dict[str, int],
    ) -> DispatchStats:
        if not queue_wait_ticks:
            return DispatchStats(
                lane_totals=dict(lane_totals),
                lane_max_concurrency=dict(lane_max_concurrency),
            )
        total = sum(queue_wait_ticks)
        max_wait = max(queue_wait_ticks)
        zero_wait = sum(1 for value in queue_wait_ticks if value == 0)
        average = total / len(queue_wait_ticks)
        return DispatchStats(
            average_queue_wait=average,
            max_queue_wait=max_wait,
            total_queue_wait=total,
            commands_with_zero_wait=zero_wait,
            lane_totals=dict(lane_totals),
            lane_max_concurrency=dict(lane_max_concurrency),
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
    "CQDeadlockError",
    "replay_dependencies",
    "SchedulingPolicy",
]
