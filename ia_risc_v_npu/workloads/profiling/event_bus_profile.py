"""Profiling helpers for observing event scheduler and bus usage."""
from __future__ import annotations

import asyncio
import json
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import sys
import math

import numpy as np

# Ensure repository paths are available for absolute imports.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
for path in (PACKAGE_ROOT, PROJECT_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.simulator.events import EventScheduler as BaseEventScheduler
from src.simulator.main import AdaptiveSimulator
from src.npu.cluster import ClusterPolicy, ClusterTask, NPUCluster
from src.simulator.memory import Bus, BusMetrics, BusRequest
from workloads.cnn_workload import generate_cnn_workload

# ABI register aliases (matches integration tests)
REG_T0 = 5
REG_T1 = 6
REG_T2 = 7


class VirtualBus:
    """Bus variant that decouples DMA scheduling from simulator global time."""

    def __init__(
        self,
        *,
        slice_bytes: int = 32,
        bandwidth_bytes_per_cycle: int = 16,
        grant_latency: int = 1,
    ) -> None:
        if slice_bytes <= 0 or bandwidth_bytes_per_cycle <= 0:
            raise ValueError("slice_bytes and bandwidth must be positive")

        self.slice_bytes = slice_bytes
        self.bandwidth_bytes_per_cycle = bandwidth_bytes_per_cycle
        self.grant_latency = grant_latency

        self.metrics = BusMetrics()
        self._available_at = 0
        self._active_until: List[int] = []
        self._completed: List[BusRequest] = []

    @property
    def now(self) -> int:
        return 0

    def sync_time(self, now: int) -> None:
        if now < 0:
            raise ValueError("now cannot be negative")
        # Intentionally ignore caller-provided time to avoid sequencing by global bus time.
        return

    def request(
        self,
        *,
        master_id: int,
        bytes: int,
        request_at: int | None = None,
    ) -> Tuple[int, int]:
        if bytes <= 0:
            raise ValueError("bytes must be greater than zero")

        request_time = max(0, request_at or 0)
        self._active_until = [deadline for deadline in self._active_until if deadline > request_time]
        queue_depth = len(self._active_until) + 1
        self.metrics.on_request(queue_depth)

        grant_time = max(request_time, self._available_at)
        start_time = grant_time + self.grant_latency
        transfer_cycles = self._calculate_transfer_cycles(bytes)
        done_at = start_time + transfer_cycles

        request = BusRequest(master_id=master_id, size_bytes=bytes, request_at=request_time)
        request.grant_at = grant_time
        request.start_at = start_time
        request.done_at = done_at
        request.transfer_cycles = transfer_cycles
        self._completed.append(request)

        wait_cycles = max(0, grant_time - request_time)
        self.metrics.on_grant(
            wait_cycles=wait_cycles,
            grant_latency=self.grant_latency,
            transfer_cycles=transfer_cycles,
        )

        self._available_at = done_at
        self._active_until.append(done_at)
        return grant_time, done_at

    def completed_requests(self) -> Tuple[BusRequest, ...]:
        return tuple(self._completed)

    def _calculate_transfer_cycles(self, size_bytes: int) -> int:
        full_slices, remainder = divmod(size_bytes, self.slice_bytes)
        slice_cycles = math.ceil(self.slice_bytes / self.bandwidth_bytes_per_cycle)
        total = full_slices * slice_cycles
        if remainder:
            total += math.ceil(remainder / self.bandwidth_bytes_per_cycle)
        return total


class ProfilingEventScheduler(BaseEventScheduler):
    """EventScheduler variant that records queue usage statistics."""

    def __init__(self) -> None:
        super().__init__()
        self.enqueue_log: List[Dict[str, Any]] = []
        self.execution_log: List[Dict[str, Any]] = []
        self.max_queue_depth: int = 0

    def schedule(self, *, timestamp: int, callback):  # type: ignore[override]
        callback_name = self._callback_name(callback)

        def wrapped() -> None:
            # Record queue depth immediately before the callback executes (after pop).
            self.execution_log.append(
                {
                    "timestamp": self.now,
                    "callback": callback_name,
                    "queue_depth_remaining": len(self._queue),
                }
            )
            callback()

        order = super().schedule(timestamp=timestamp, callback=wrapped)
        queue_depth = len(self._queue)
        if queue_depth > self.max_queue_depth:
            self.max_queue_depth = queue_depth
        self.enqueue_log.append(
            {
                "timestamp": timestamp,
                "callback": callback_name,
                "queue_depth_after_push": queue_depth,
                "order": order,
            }
        )
        return order

    @staticmethod
    def _callback_name(callback: Any) -> str:
        if hasattr(callback, "__name__"):
            return str(callback.__name__)
        return callback.__class__.__name__


@contextmanager
def install_profiling_scheduler() -> Iterable[None]:
    """Temporarily replace EventScheduler with the profiling variant."""

    import src.simulator.events as events_module
    import src.simulator.main as main_module

    original_events = events_module.EventScheduler
    original_main = main_module.EventScheduler

    events_module.EventScheduler = ProfilingEventScheduler
    main_module.EventScheduler = ProfilingEventScheduler
    try:
        yield
    finally:
        events_module.EventScheduler = original_events
        main_module.EventScheduler = original_main


def _seed_program_state(simulator: AdaptiveSimulator, input_shape: Tuple[int, ...], kernel_shape: Tuple[int, ...]) -> None:
    input_size = int(np.prod(input_shape))
    weight_size = int(np.prod(kernel_shape))

    input_data = np.arange(1, input_size + 1, dtype=np.uint32).reshape(input_shape)
    weights = np.arange(1, weight_size + 1, dtype=np.uint32).reshape(kernel_shape)

    input_addr = 0x20000
    weights_addr = 0x30000
    output_addr = 0x40000

    simulator.risc_v_engine.registers[REG_T0] = input_addr
    simulator.risc_v_engine.registers[REG_T1] = weights_addr
    simulator.risc_v_engine.registers[REG_T2] = output_addr

    simulator.bus.write(input_addr, input_data.tobytes())
    simulator.bus.write(weights_addr, weights.tobytes())


def _summarize_scheduler(scheduler: ProfilingEventScheduler) -> Dict[str, Any]:
    queue_depths = [entry["queue_depth_after_push"] for entry in scheduler.enqueue_log]
    depth_histogram = Counter(queue_depths)
    callbacks = Counter(entry["callback"] for entry in scheduler.enqueue_log)
    return {
        "events_scheduled": len(scheduler.enqueue_log),
        "max_queue_depth": scheduler.max_queue_depth,
        "queue_depth_histogram": dict(sorted(depth_histogram.items())),
        "callbacks": dict(sorted(callbacks.items())),
    }


def _summarize_bus(simulator: AdaptiveSimulator) -> Dict[str, Any]:
    requests = simulator.bus.completed_requests()
    count_by_master: Dict[int, int] = Counter(req.master_id for req in requests)
    bytes_by_master: Dict[int, int] = defaultdict(int)
    wait_by_master: Dict[int, int] = defaultdict(int)

    for req in requests:
        bytes_by_master[req.master_id] += req.size_bytes
        if req.grant_at is not None:
            wait_by_master[req.master_id] += max(0, req.grant_at - req.request_at)

    metrics = simulator.bus.metrics.snapshot()
    return {
        "completed_requests": dict(sorted(count_by_master.items())),
        "bytes_transferred": dict(sorted(bytes_by_master.items())),
        "total_wait_cycles": dict(sorted(wait_by_master.items())),
        "bus_metrics": metrics,
    }


def profile_cnn_workload(input_shape: Tuple[int, ...], kernel_shape: Tuple[int, ...]) -> Dict[str, Any]:
    simulator = AdaptiveSimulator()
    _seed_program_state(simulator, input_shape, kernel_shape)

    workload = generate_cnn_workload(input_shape, kernel_shape)
    workload.append(0x0000006F)  # halt instruction
    simulator.load_program(workload)

    with install_profiling_scheduler():
        report = asyncio.run(simulator.run_simulation(max_cycles=len(workload) * 20))

    scheduler = simulator.scheduler
    if not isinstance(scheduler, ProfilingEventScheduler):
        raise RuntimeError("Expected ProfilingEventScheduler to be installed")

    scheduler_summary = _summarize_scheduler(scheduler)
    bus_summary = _summarize_bus(simulator)

    return {
        "input_shape": input_shape,
        "kernel_shape": kernel_shape,
        "instructions": report.instructions,
        "cycles": report.cycles,
        "mips": report.mips,
        "scheduler": scheduler_summary,
        "bus": bus_summary,
    }


def _summarize_requests(bus: Any) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for req in bus.completed_requests():
        summary.append(
            {
                "master_id": req.master_id,
                "size_bytes": req.size_bytes,
                "request_at": req.request_at,
                "grant_at": req.grant_at,
                "start_at": req.start_at,
                "done_at": req.done_at,
                "transfer_cycles": req.transfer_cycles,
            }
        )
    return summary


def _flush_cluster(cluster: NPUCluster, *, horizon: int | None = None) -> None:
    if horizon is None:
        horizon = max(
            (result.task.issue_at + result.task.compute_cycles for result in cluster.history),
            default=0,
        )
        horizon += 1_000

    cluster.flush_deferred_dma(horizon)

    bus = cluster.bus
    if hasattr(bus, "sync_time"):
        bus.sync_time(horizon)


def profile_npu_dma(tasks: List[ClusterTask]) -> Dict[str, Any]:
    simulator = AdaptiveSimulator()
    results = [simulator.npu_cluster.submit(task) for task in tasks]

    horizon = max((task.issue_at + task.compute_cycles for task in tasks), default=0) + 1_000
    _flush_cluster(simulator.npu_cluster, horizon=horizon)

    timeline: List[Dict[str, Any]] = []
    for result in results:
        timeline.append(
            {
                "task": result.task.name,
                "issue_at": result.task.issue_at,
                "input_grant_at": result.input_grant_at,
                "input_done_at": result.input_done_at,
                "compute_start_at": result.compute_start_at,
                "compute_done_at": result.compute_done_at,
                "output_grant_at": result.output_grant_at,
                "output_done_at": result.output_done_at,
                "done_at": result.done_at,
                "core_id": result.core_id,
            }
        )

    bus_summary = _summarize_bus(simulator)
    requests = _summarize_requests(simulator.bus)

    return {
        "tasks": [
            {
                "name": task.name,
                "input_bytes": task.input_bytes,
                "output_bytes": task.output_bytes,
                "compute_cycles": task.compute_cycles,
                "issue_at": task.issue_at,
            }
            for task in tasks
        ],
        "timeline": timeline,
        "bus": bus_summary,
        "requests": requests,
    }


def profile_cpu_npu_contention() -> Dict[str, Any]:
    bus = Bus()
    cluster = NPUCluster(bus, cores=2, dma_master_id=1, policy=ClusterPolicy.ROUND_ROBIN)

    cpu_schedule = [0, 20, 40, 60, 80, 100]
    cpu_results: List[Dict[str, Any]] = []

    for idx, request_at in enumerate(cpu_schedule):
        bus.sync_time(request_at)
        grant_at, done_at = bus.request(master_id=0, bytes=64, request_at=request_at)
        cpu_results.append(
            {
                "request_id": idx,
                "request_at": request_at,
                "grant_at": grant_at,
                "done_at": done_at,
            }
        )

    npu_tasks = [
        ClusterTask(input_bytes=256, output_bytes=128, compute_cycles=60, issue_at=5, name="npu_0"),
        ClusterTask(input_bytes=128, output_bytes=128, compute_cycles=80, issue_at=45, name="npu_1"),
        ClusterTask(input_bytes=192, output_bytes=192, compute_cycles=100, issue_at=85, name="npu_2"),
    ]

    results = [cluster.submit(task) for task in npu_tasks]

    horizon = max((task.issue_at + task.compute_cycles for task in npu_tasks), default=0) + 1_000
    _flush_cluster(cluster, horizon=horizon)

    npu_timeline: List[Dict[str, Any]] = []
    for result in results:
        npu_timeline.append(
            {
                "task": result.task.name,
                "issue_at": result.task.issue_at,
                "input_grant_at": result.input_grant_at,
                "input_done_at": result.input_done_at,
                "compute_start_at": result.compute_start_at,
                "compute_done_at": result.compute_done_at,
                "output_grant_at": result.output_grant_at,
                "output_done_at": result.output_done_at,
                "done_at": result.done_at,
                "core_id": result.core_id,
            }
        )

    requests = _summarize_requests(cluster.bus)
    bus_metrics = cluster.bus.metrics.snapshot()

    return {
        "cpu_requests": cpu_results,
        "npu_tasks": [
            {
                "name": task.name,
                "input_bytes": task.input_bytes,
                "output_bytes": task.output_bytes,
                "compute_cycles": task.compute_cycles,
                "issue_at": task.issue_at,
            }
            for task in npu_tasks
        ],
        "npu_timeline": npu_timeline,
        "requests": requests,
        "bus_metrics": bus_metrics,
    }


def profile_virtual_npu_dma(tasks: List[ClusterTask]) -> Dict[str, Any]:
    bus = VirtualBus()
    cluster = NPUCluster(bus, cores=2, dma_master_id=1, policy=ClusterPolicy.MIN_FINISH_TIME)

    results = [cluster.submit(task) for task in tasks]

    horizon = max((task.issue_at + task.compute_cycles for task in tasks), default=0) + 1_000
    _flush_cluster(cluster, horizon=horizon)

    timeline: List[Dict[str, Any]] = []
    for result in results:
        timeline.append(
            {
                "task": result.task.name,
                "issue_at": result.task.issue_at,
                "input_grant_at": result.input_grant_at,
                "input_done_at": result.input_done_at,
                "compute_start_at": result.compute_start_at,
                "compute_done_at": result.compute_done_at,
                "output_grant_at": result.output_grant_at,
                "output_done_at": result.output_done_at,
                "done_at": result.done_at,
                "core_id": result.core_id,
            }
        )

    requests = _summarize_requests(bus)
    bus_metrics = bus.metrics.snapshot()

    return {
        "tasks": [
            {
                "name": task.name,
                "input_bytes": task.input_bytes,
                "output_bytes": task.output_bytes,
                "compute_cycles": task.compute_cycles,
                "issue_at": task.issue_at,
            }
            for task in tasks
        ],
        "timeline": timeline,
        "requests": requests,
        "bus_metrics": bus_metrics,
    }


def replay_virtual_dma(
    requests: List[Dict[str, Any]],
    *,
    slice_bytes: int = 32,
    bandwidth_bytes_per_cycle: int = 16,
    grant_latency: int = 1,
) -> Dict[str, Any]:
    bus = Bus(
        slice_bytes=slice_bytes,
        bandwidth_bytes_per_cycle=bandwidth_bytes_per_cycle,
        grant_latency=grant_latency,
    )
    replay_log: List[Dict[str, Any]] = []

    for entry in sorted(requests, key=lambda item: (item.get("grant_at", 0), item.get("request_at", 0))):
        request_at = entry.get("grant_at", entry.get("request_at", 0))
        issue_time = max(bus.now, request_at)
        bus.sync_time(issue_time)
        grant_at, done_at = bus.request(
            master_id=entry.get("master_id", 1),
            bytes=entry.get("size_bytes", 0),
            request_at=issue_time,
        )
        replay_log.append(
            {
                "original_grant": entry.get("grant_at"),
                "original_done": entry.get("done_at"),
                "replay_grant": grant_at,
                "replay_done": done_at,
                "size_bytes": entry.get("size_bytes"),
                "master_id": entry.get("master_id"),
            }
        )

    return {
        "requests": replay_log,
        "bus_metrics": bus.metrics.snapshot(),
    }


def main() -> None:
    scenarios = [
        ((1, 3, 3), (1, 1, 2, 2)),
        ((2, 4, 4), (3, 2, 2, 2)),
        ((1, 5, 5), (2, 1, 3, 3)),
    ]
    cnn_results = [profile_cnn_workload(*scenario) for scenario in scenarios]

    npu_tasks = [
        ClusterTask(
            input_bytes=256,
            output_bytes=256,
            compute_cycles=120,
            issue_at=0,
            name="task_0",
        ),
        ClusterTask(
            input_bytes=256,
            output_bytes=256,
            compute_cycles=120,
            issue_at=40,
            name="task_1",
        ),
        ClusterTask(
            input_bytes=256,
            output_bytes=256,
            compute_cycles=120,
            issue_at=80,
            name="task_2",
        ),
    ]
    npu_results = profile_npu_dma(npu_tasks)

    contention = profile_cpu_npu_contention()
    virtual_npu = profile_virtual_npu_dma(npu_tasks)
    virtual_replay = replay_virtual_dma(virtual_npu["requests"])

    payload = {
        "cpu_cnn": cnn_results,
        "npu_dma": npu_results,
        "cpu_npu_contention": contention,
        "virtual_npu_dma": virtual_npu,
        "virtual_replay": virtual_replay,
    }

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
