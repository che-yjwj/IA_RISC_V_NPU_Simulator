"""Tensor engine timing approximations for GEMM workloads."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class TensorEngineTimingModel:
    """Estimate execution time for GEMM tiles on the tensor engine."""

    peak_flops_per_cycle: int = 512
    launch_overhead: int = 8
    epilogue_overhead: int = 6
    cores: int = 1

    def update_cores(self, cores: int) -> None:
        self.cores = max(1, int(cores))

    def estimate_cycles(self, m: int, n: int, k: int) -> int:
        if min(m, n, k) <= 0:
            return self.launch_overhead

        operations = 2 * m * n * k
        throughput = max(1, self.peak_flops_per_cycle * self.cores)
        compute_cycles = max(1, math.ceil(operations / throughput))
        return self.launch_overhead + compute_cycles + self.epilogue_overhead
