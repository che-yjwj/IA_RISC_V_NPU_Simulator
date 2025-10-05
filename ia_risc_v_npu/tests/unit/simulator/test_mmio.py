from __future__ import annotations

from src.npu.cluster import ClusterPolicy, NPUCluster
from src.simulator.memory import Bus
from src.simulator.mmio import MMIO


def _make_bus() -> Bus:
    return Bus(slice_bytes=16, bandwidth_bytes_per_cycle=8, grant_latency=1)


def _write(mmio: MMIO, offset: int, value: int) -> None:
    mmio.write(offset, value.to_bytes(4, "little"))


def _read(mmio: MMIO, offset: int) -> int:
    return int.from_bytes(mmio.read(offset, 4), "little")


def test_mmio_launches_task_and_updates_status() -> None:
    cluster = NPUCluster(_make_bus(), cores=1)
    mmio = MMIO(cluster)

    _write(mmio, MMIO.REG_INPUT_ADDR, 0x1000)
    _write(mmio, MMIO.REG_INPUT_SIZE, 32)
    _write(mmio, MMIO.REG_OUTPUT_ADDR, 0x2000)
    _write(mmio, MMIO.REG_OUTPUT_SIZE, 16)
    _write(mmio, MMIO.REG_COMPUTE_CYCLES, 12)

    _write(mmio, MMIO.REG_CONTROL, MMIO.CONTROL_LAUNCH)

    cluster.schedule(0)
    cluster.schedule(1_000)

    submission = mmio.last_submission
    assert submission is not None
    assert submission.task.input_bytes == 32
    assert submission.task.output_bytes == 16
    assert submission.task.compute_cycles == 12
    assert submission.input_address == 0x1000
    assert submission.output_address == 0x2000
    assert submission.core_id == 0
    assert cluster.history[-1] is submission
    assert cluster.bus.metrics.completed_requests == 2

    assert _read(mmio, MMIO.REG_LAST_DONE) == submission.done_at
    assert _read(mmio, MMIO.REG_LAST_CORE) == submission.core_id


def test_policy_round_robin_rotates_cores() -> None:
    cluster = NPUCluster(_make_bus(), cores=2, policy=ClusterPolicy.ROUND_ROBIN)
    mmio = MMIO(cluster)

    _write(mmio, MMIO.REG_POLICY, 1)
    _write(mmio, MMIO.REG_INPUT_SIZE, 16)
    _write(mmio, MMIO.REG_COMPUTE_CYCLES, 4)
    _write(mmio, MMIO.REG_CONTROL, MMIO.CONTROL_LAUNCH)

    _write(mmio, MMIO.REG_INPUT_SIZE, 16)
    _write(mmio, MMIO.REG_COMPUTE_CYCLES, 4)
    _write(mmio, MMIO.REG_CONTROL, MMIO.CONTROL_LAUNCH)

    cluster.schedule(0)

    submissions = cluster.history
    assert len(submissions) == 2
    assert submissions[0].core_id == 0
    assert submissions[1].core_id == 1


def test_issue_at_defers_dma_request_time() -> None:
    cluster = NPUCluster(_make_bus(), cores=1)
    mmio = MMIO(cluster)

    _write(mmio, MMIO.REG_INPUT_SIZE, 8)
    _write(mmio, MMIO.REG_COMPUTE_CYCLES, 2)
    _write(mmio, MMIO.REG_ISSUE_AT, 25)
    _write(mmio, MMIO.REG_CONTROL, MMIO.CONTROL_LAUNCH)

    cluster.schedule(25)
    cluster.schedule(1_000)

    submission = mmio.last_submission
    assert submission is not None
    assert submission.task.issue_at == 25
    assert submission.input_grant_at >= 25
    assert submission.compute_start_at >= 25
