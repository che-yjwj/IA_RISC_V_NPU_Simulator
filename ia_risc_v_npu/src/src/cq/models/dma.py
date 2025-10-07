"""Row-based DMA transfer timing estimates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(slots=True)
class DMATransferPlan:
    rows: int
    row_bytes: int
    total_bytes: int
    estimated_cycles: int


@dataclass(slots=True)
class DMATimingModel:
    """Compute coarse transfer timings for DMA operations."""

    setup_cycles: int = 4
    row_overhead_cycles: int = 1
    bytes_per_cycle: int = 32
    stride_penalty: int = 2

    def plan(
        self,
        shape: Sequence[int],
        strides: Optional[Sequence[int]] = None,
        *,
        element_bytes: int = 4,
    ) -> DMATransferPlan:
        if len(shape) != 2:
            raise ValueError("DMA shape must contain [rows, cols]")
        rows = int(shape[0])
        cols = int(shape[1])
        if rows <= 0 or cols <= 0:
            raise ValueError("DMA shape must contain positive dimensions")

        row_bytes = cols * element_bytes
        data_cycles = math.ceil(row_bytes / max(1, self.bytes_per_cycle))

        penalty = 0
        if strides is not None and len(strides) >= 1:
            row_stride = int(strides[0])
            if row_stride > cols:
                slack = row_stride - cols
                penalty = slack * self.stride_penalty

        total_cycles = self.setup_cycles + rows * (
            self.row_overhead_cycles + data_cycles + penalty
        )
        total_bytes = rows * row_bytes

        return DMATransferPlan(
            rows=rows,
            row_bytes=row_bytes,
            total_bytes=total_bytes,
            estimated_cycles=total_cycles,
        )
