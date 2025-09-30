# -*- coding: utf-8 -*-
"""NPU 클러스터 및 DMA 파이프라인 스케줄러."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Callable, Optional, Union

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


@dataclass(slots=True)
class DeferredDMA:
    """지연 실행되는 DMA 요청 정보."""

    task: ClusterTask
    channel: str
    size_bytes: int
    scheduled_at: int
    order: int
    result: SubmissionResult

    def channel_priority(self) -> int:
        if self.channel == "input":
            return 0
        if self.channel == "output":
            return 1
        return 2


class NPUCluster:
    """코어/버스 공유를 고려한 간단한 NPU 클러스터 모델."""

    def __init__(
        self,
        bus: Bus,
        *,
        cores: int = 1,
        dma_master_id: Union[int, IntEnum] = 1,
        policy: ClusterPolicy = ClusterPolicy.MIN_FINISH_TIME,
        compute_engine: Optional[NPU] = None,
    ) -> None:
        if not isinstance(dma_master_id, (int, IntEnum)):
            raise TypeError("dma_master_id must be an integer or IntEnum")
        dma_master = int(dma_master_id)

        if cores <= 0:
            raise ValueError("코어 개수는 1 이상이어야 합니다.")

        self.bus = bus
        self.cores = cores
        self.dma_master_id = dma_master
        self.policy = policy
        self.compute_engine = compute_engine or NPU()

        self.core_free_at = [0 for _ in range(cores)]
        self._core_actual_free = [0 for _ in range(cores)]
        self._core_pending_cycles = [0 for _ in range(cores)]
        self._rr_index = 0
        self._dma_available_at = {
            "input": 0,
            "output": 0,
        }
        self.history: list[SubmissionResult] = []
        self._total_compute_cycles = 0
        self._total_wait_cycles = 0
        self._last_completion = 0
        self._pending_dma: list[DeferredDMA] = []
        self._dma_sequence = itertools.count()

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
        self.flush_deferred_dma(task.issue_at)

        for idx in range(self.cores):
            self.core_free_at[idx] = self._core_actual_free[idx] + self._core_pending_cycles[idx]
        core_id = self._select_core(task, effective_policy)

        base_ready = self._core_actual_free[core_id] + self._core_pending_cycles[core_id]
        predicted_start = max(base_ready, task.issue_at)
        predicted_done = predicted_start + task.compute_cycles
        self._core_pending_cycles[core_id] += max(0, task.compute_cycles)
        self.core_free_at[core_id] = self._core_actual_free[core_id] + self._core_pending_cycles[core_id]

        result = SubmissionResult(
            task=task,
            core_id=core_id,
            policy=effective_policy,
            input_grant_at=-1,
            input_done_at=-1,
            compute_start_at=-1,
            compute_done_at=-1,
            output_grant_at=-1,
            output_done_at=-1,
            done_at=-1,
            input_address=task.input_address,
            output_address=task.output_address,
        )

        self._pending_dma.append(
            DeferredDMA(
                task=task,
                channel="input",
                size_bytes=task.input_bytes,
                scheduled_at=task.issue_at,
                order=next(self._dma_sequence),
                result=result,
            )
        )
        self._pending_dma.append(
            DeferredDMA(
                task=task,
                channel="output",
                size_bytes=task.output_bytes,
                scheduled_at=task.issue_at,
                order=next(self._dma_sequence),
                result=result,
            )
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

    def flush_deferred_dma(self, now: int) -> None:
        """현재 시각까지 예정된 DMA 요청을 실제 버스에 재생한다."""

        if now < 0:
            raise ValueError("now는 음수가 될 수 없습니다.")
        if not self._pending_dma:
            return

        ordered = sorted(
            self._pending_dma,
            key=lambda dma: (dma.scheduled_at, dma.channel_priority(), dma.order),
        )

        remaining: list[DeferredDMA] = []
        for dma in ordered:
            request_time = self._resolve_deferred_request_time(dma)
            if request_time is None or request_time > now:
                if request_time is not None:
                    dma.scheduled_at = request_time
                remaining.append(dma)
                continue
            self._execute_deferred_dma(dma, request_time)

        self._pending_dma = remaining

    def _resolve_deferred_request_time(self, dma: DeferredDMA) -> Optional[int]:
        channel = dma.channel
        available_at = self._dma_available_at.get(channel, 0)

        if channel == "input":
            ready = max(dma.task.issue_at, dma.scheduled_at, available_at)
            return max(ready, self.bus.now)

        if channel == "output":
            if dma.result.compute_done_at < 0:
                return None
            ready = max(dma.result.compute_done_at, dma.scheduled_at, available_at)
            dma.scheduled_at = max(dma.scheduled_at, dma.result.compute_done_at)
            return max(ready, self.bus.now)

        ready = max(dma.task.issue_at, dma.scheduled_at, available_at)
        return max(ready, self.bus.now)

    def _execute_deferred_dma(self, dma: DeferredDMA, request_time: int) -> None:
        channel = dma.channel
        size_bytes = dma.size_bytes
        if size_bytes < 0:
            raise ValueError("DMA 전송 크기는 음수가 될 수 없습니다.")

        if size_bytes == 0:
            anchor = max(request_time, self.bus.now, self._dma_available_at.get(channel, 0))
            grant_at = anchor
            done_at = anchor
        else:
            self.bus.sync_time(request_time)
            grant_at, done_at = self.bus.request(
                master_id=self.dma_master_id,
                bytes=size_bytes,
                request_at=request_time,
            )

        self._dma_available_at[channel] = done_at

        result = dma.result
        task = dma.task

        if channel == "input":
            result.input_grant_at = grant_at
            result.input_done_at = done_at
            core_id = result.core_id
            compute_start = max(self._core_actual_free[core_id], done_at)
            result.compute_start_at = compute_start
            compute_done = compute_start + task.compute_cycles
            result.compute_done_at = compute_done
            remaining = self._core_pending_cycles[core_id] - max(0, task.compute_cycles)
            self._core_pending_cycles[core_id] = max(0, remaining)
            self._core_actual_free[core_id] = compute_done
            self.core_free_at[core_id] = self._core_actual_free[core_id] + self._core_pending_cycles[core_id]

            wait_cycles = max(0, compute_start - task.issue_at)
            self._total_wait_cycles += wait_cycles
            self._total_compute_cycles += max(0, task.compute_cycles)

            if task.operation is not None:
                task.operation(self.compute_engine)

        elif channel == "output":
            result.output_grant_at = grant_at
            result.output_done_at = done_at
            result.done_at = max(result.compute_done_at, done_at)
            core_id = result.core_id
            predicted = self._core_actual_free[core_id] + self._core_pending_cycles[core_id]
            self.core_free_at[core_id] = max(predicted, result.done_at)
            self._last_completion = max(self._last_completion, result.done_at)
        else:
            # Other channels can simply record timing if needed in future.
            pass

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
