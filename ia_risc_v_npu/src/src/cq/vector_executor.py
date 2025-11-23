"""Vector execution micro-step planner for CQ vector operations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class VectorMicroStep:
    """Single micro-step in the vector pipeline."""

    stage: str
    cycles: int
    bytes_accessed: int


@dataclass(slots=True)
class VectorExecutionPlan:
    """Expanded vector plan capturing micro-steps and aggregate metrics."""

    steps: List[VectorMicroStep]
    total_cycles: int
    total_bytes: int


class VectorExecutor:
    """Plan vector CQ commands into micro-steps with timing estimates."""

    def __init__(
        self,
        *,
        vector_width: int = 4,
        bytes_per_cycle: int = 16,
        load_overhead: int = 2,
        store_overhead: int = 2,
        compute_overhead: int = 1,
    ) -> None:
        self.vector_width = max(1, int(vector_width))
        self.bytes_per_cycle = max(1, int(bytes_per_cycle))
        self.load_overhead = max(0, int(load_overhead))
        self.store_overhead = max(0, int(store_overhead))
        self.compute_overhead = max(0, int(compute_overhead))

    def plan_add(self, *, length: int, stride: int = 1, element_bytes: int = 4) -> VectorExecutionPlan:
        if length <= 0:
            return VectorExecutionPlan(steps=[], total_cycles=0, total_bytes=0)

        stride = max(1, int(stride))
        element_bytes = max(1, int(element_bytes))
        segments = math.ceil(length / self.vector_width)

        steps: List[VectorMicroStep] = []
        total_cycles = 0
        total_bytes = 0

        for segment in range(segments):
            remaining = max(0, length - segment * self.vector_width)
            active = min(self.vector_width, remaining)
            span = (active - 1) * stride + 1
            load_bytes = span * element_bytes * 2  # src0 + src1
            store_bytes = active * element_bytes

            load_cycles = self.load_overhead + math.ceil(load_bytes / self.bytes_per_cycle)
            compute_cycles = self.compute_overhead + max(1, math.ceil(active / self.vector_width))
            store_cycles = self.store_overhead + math.ceil(store_bytes / self.bytes_per_cycle)

            steps.append(
                VectorMicroStep(
                    stage="load",
                    cycles=load_cycles,
                    bytes_accessed=load_bytes,
                )
            )
            steps.append(
                VectorMicroStep(
                    stage="execute",
                    cycles=compute_cycles,
                    bytes_accessed=0,
                )
            )
            steps.append(
                VectorMicroStep(
                    stage="store",
                    cycles=store_cycles,
                    bytes_accessed=store_bytes,
                )
            )

            total_cycles += load_cycles + compute_cycles + store_cycles
            total_bytes += load_bytes + store_bytes

        return VectorExecutionPlan(steps=steps, total_cycles=total_cycles, total_bytes=total_bytes)


__all__ = [
    "VectorExecutor",
    "VectorExecutionPlan",
    "VectorMicroStep",
]
