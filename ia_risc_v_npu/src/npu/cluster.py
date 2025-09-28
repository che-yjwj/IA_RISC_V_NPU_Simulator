# -*- coding: utf-8 -*-
"""NPU 클러스터 및 DMA 파이프라인 스케줄러."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from src.npu.model import NPU
from src.simulator.memory import Bus


OperationCallable = Callable[[NPU], object]


class ClusterPolicy(str, Enum):
    """코어 선택 정책."""

    MIN_FINISH_TIME = "min_finish_time"
    ROUND_ROBIN = "rr"


@dataclass(slots=True)
class ClusterTask:
    """NPU 클러스터에 제출되는 작업 요청."""

    input_bytes: int
    output_bytes: int
    compute_cycles: int
    issue_at: int = 0
    name: str = ""
    operation: Optional[OperationCallable] = None
    input_address: Optional[int] = None
    output_address: Optional[int] = None


@dataclass(slots=True)
class SubmissionResult:
    """작업 실행 타임라인."""

    task: ClusterTask
    core_id: int
    policy: ClusterPolicy
    input_grant_at: int
    input_done_at: int
    compute_start_at: int
    compute_done_at: int
    output_grant_at: int
    output_done_at: int
    done_at: int
    input_address: Optional[int] = None
    output_address: Optional[int] = None


class NPUCluster:
    """코어/버스 공유를 고려한 간단한 NPU 클러스터 모델."""

    def __init__(
        self,
        bus: Bus,
        *,
        cores: int = 1,
        dma_master_id: int = 1,
        policy: ClusterPolicy = ClusterPolicy.MIN_FINISH_TIME,
        compute_engine: Optional[NPU] = None,
    ) -> None:
        if cores <= 0:
            raise ValueError("코어 개수는 1 이상이어야 합니다.")

        self.bus = bus
        self.cores = cores
        self.dma_master_id = dma_master_id
        self.policy = policy
        self.compute_engine = compute_engine or NPU()

        self.core_free_at = [0 for _ in range(cores)]
        self._rr_index = 0
        self._dma_available_at = {
            "input": 0,
            "output": 0,
        }
        self.history: list[SubmissionResult] = []
        self._total_compute_cycles = 0
        self._total_wait_cycles = 0
        self._last_completion = 0

    def submit(
        self,
        task: ClusterTask,
        *,
        policy: Optional[ClusterPolicy] = None,
    ) -> SubmissionResult:
        """작업을 스케줄링하고 완료 시각을 반환한다."""

        if task.input_bytes < 0 or task.output_bytes < 0:
            raise ValueError("DMA 전송 크기는 음수가 될 수 없습니다.")
        if task.compute_cycles < 0:
            raise ValueError("compute_cycles는 음수가 될 수 없습니다.")

        effective_policy = policy or self.policy
        core_id = self._select_core(task, effective_policy)

        input_grant_at, input_done_at = self._perform_dma(
            size_bytes=task.input_bytes,
            request_at=task.issue_at,
            channel="input",
        )

        compute_start_at = max(self.core_free_at[core_id], input_done_at)
        compute_done_at = compute_start_at + task.compute_cycles
        wait_cycles = max(0, compute_start_at - task.issue_at)
        self._total_wait_cycles += wait_cycles
        self._total_compute_cycles += max(0, task.compute_cycles)

        if task.operation is not None:
            task.operation(self.compute_engine)

        output_grant_at, output_done_at = self._perform_dma(
            size_bytes=task.output_bytes,
            request_at=compute_done_at,
            channel="output",
        )

        done_at = max(compute_done_at, output_done_at)
        self.core_free_at[core_id] = done_at
        self._last_completion = max(self._last_completion, done_at)

        result = SubmissionResult(
            task=task,
            core_id=core_id,
            policy=effective_policy,
            input_grant_at=input_grant_at,
            input_done_at=input_done_at,
            compute_start_at=compute_start_at,
            compute_done_at=compute_done_at,
            output_grant_at=output_grant_at,
            output_done_at=output_done_at,
            done_at=done_at,
            input_address=task.input_address,
            output_address=task.output_address,
        )

        self.history.append(result)
        return result

    def metrics(self, *, sim_time: int | None = None) -> dict[str, float | int]:
        horizon = sim_time if sim_time and sim_time > 0 else self._last_completion
        capacity = horizon * self.cores if horizon > 0 else 0
        utilization = (
            self._total_compute_cycles / capacity if capacity > 0 else 0.0
        )
        return {
            "cores": self.cores,
            "tasks": len(self.history),
            "utilization": utilization,
            "compute_cycles": self._total_compute_cycles,
            "wait_cycles": self._total_wait_cycles,
            "horizon_cycles": horizon,
        }

    def _perform_dma(self, *, size_bytes: int, request_at: int, channel: str) -> tuple[int, int]:
        if channel not in self._dma_available_at:
            raise ValueError(f"Unknown DMA channel: {channel}")

        if size_bytes == 0:
            anchor = max(request_at, self.bus.now, self._dma_available_at[channel])
            self._dma_available_at[channel] = anchor
            return anchor, anchor

        if size_bytes < 0:
            raise ValueError("DMA 전송 크기는 음수가 될 수 없습니다.")

        request_time = max(request_at, self.bus.now, self._dma_available_at[channel])
        self.bus.sync_time(request_time)
        grant_at, done_at = self.bus.request(
            master_id=self.dma_master_id,
            bytes=size_bytes,
            request_at=request_time,
        )
        self._dma_available_at[channel] = done_at
        return grant_at, done_at

    def _select_core(self, task: ClusterTask, policy: ClusterPolicy) -> int:
        if policy == ClusterPolicy.ROUND_ROBIN:
            core = self._rr_index
            self._rr_index = (self._rr_index + 1) % self.cores
            return core

        best_core = 0
        best_finish = None
        for idx, ready_at in enumerate(self.core_free_at):
            start_time = max(ready_at, task.issue_at)
            predicted_finish = start_time + task.compute_cycles
            if best_finish is None or predicted_finish < best_finish:
                best_finish = predicted_finish
                best_core = idx
        return best_core


__all__ = [
    "ClusterPolicy",
    "ClusterTask",
    "SubmissionResult",
    "NPUCluster",
]
