from __future__ import annotations

from typing import Dict

from src.npu.cluster import ClusterPolicy, ClusterTask, NPUCluster
from src.simulator.memory import Bus


def _make_bus() -> Bus:
    return Bus(slice_bytes=16, bandwidth_bytes_per_cycle=8, grant_latency=1)


def test_single_core_timeline() -> None:
    bus = _make_bus()
    cluster = NPUCluster(bus, cores=1)

    task = ClusterTask(
        name="vec-add",
        input_bytes=32,
        output_bytes=16,
        compute_cycles=10,
        issue_at=0,
    )

    result = cluster.submit(task)

    cluster.flush_deferred_dma(0)
    assert result.input_grant_at == 0
    assert result.input_done_at == 5
    assert result.compute_start_at == 5
    assert result.compute_done_at == 15

    cluster.flush_deferred_dma(20)
    assert result.output_grant_at == 15
    assert result.output_done_at == 18
    assert result.done_at == 18
    assert cluster.core_free_at[0] == 18
    assert bus.metrics.completed_requests == 2


def test_min_finish_policy_prefers_earliest_core() -> None:
    bus = _make_bus()
    cluster = NPUCluster(bus, cores=2)

    slow_task = ClusterTask(name="slow", input_bytes=16, output_bytes=0, compute_cycles=40)
    cluster.submit(slow_task, policy=ClusterPolicy.ROUND_ROBIN)  # core 0
    slower_task = ClusterTask(
        name="slower", input_bytes=16, output_bytes=0, compute_cycles=80
    )
    cluster.submit(slower_task, policy=ClusterPolicy.ROUND_ROBIN)  # core 1

    quick_task = ClusterTask(
        name="quick",
        input_bytes=0,
        output_bytes=0,
        compute_cycles=5,
        issue_at=20,
    )

    result = cluster.submit(quick_task, policy=ClusterPolicy.MIN_FINISH_TIME)

    cluster.flush_deferred_dma(quick_task.issue_at)
    cluster.flush_deferred_dma(100)

    assert result.core_id == 0
    assert result.compute_start_at >= 20
    assert result.compute_done_at == result.compute_start_at + 5


def test_round_robin_policy_rotates_cores() -> None:
    bus = _make_bus()
    cluster = NPUCluster(bus, cores=2, policy=ClusterPolicy.ROUND_ROBIN)

    task_a = ClusterTask(name="a", input_bytes=16, output_bytes=0, compute_cycles=4)
    task_b = ClusterTask(name="b", input_bytes=16, output_bytes=0, compute_cycles=4)

    result_a = cluster.submit(task_a)
    result_b = cluster.submit(task_b)

    assert result_a.core_id == 0
    assert result_b.core_id == 1


def test_submit_handles_zero_dma_and_invokes_operation() -> None:
    bus = _make_bus()
    cluster = NPUCluster(bus, cores=1)
    marker: Dict[str, bool] = {"called": False}

    def operation(_npu: object) -> object:
        marker["called"] = True
        return None

    task = ClusterTask(
        name="noop",
        input_bytes=0,
        output_bytes=0,
        compute_cycles=7,
        issue_at=3,
        operation=operation,
    )

    result = cluster.submit(task)

    cluster.flush_deferred_dma(task.issue_at)
    cluster.flush_deferred_dma(task.issue_at + 10)

    assert marker["called"] is True
    assert result.input_grant_at == 3
    assert result.input_done_at == 3
    assert result.compute_start_at == result.input_done_at
    assert result.compute_done_at == result.compute_start_at + 7
    assert result.output_done_at == result.compute_done_at
    assert bus.metrics.completed_requests == 0


def test_cluster_metrics_reports_utilisation() -> None:
    bus = _make_bus()
    cluster = NPUCluster(bus, cores=2)

    task = ClusterTask(
        name="conv",
        input_bytes=32,
        output_bytes=16,
        compute_cycles=12,
        issue_at=5,
    )

    cluster.submit(task)
    cluster.flush_deferred_dma(100)
    metrics = cluster.metrics(sim_time=40)

    assert metrics["cores"] == 2
    assert metrics["tasks"] == 1
    assert 0.0 <= metrics["utilization"] <= 1.0
    assert metrics["wait_cycles"] >= 0
