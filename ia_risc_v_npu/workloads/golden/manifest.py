"""Golden workload catalog for the CQ accuracy guard path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, Mapping, Optional, Tuple

_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class GoldenWorkload:
    """Metadata describing a single CQ golden workload candidate."""

    workload_id: str
    plan_relpath: str
    trace_relpath: str
    config_relpath: str
    description: str
    accuracy_summary_relpath: Optional[str]
    tags: Tuple[str, ...] = ()

    def plan_path(self, root: Optional[Path] = None) -> Path:
        base = root if root is not None else _ROOT
        return Path(base, self.plan_relpath)

    def trace_path(self, root: Optional[Path] = None) -> Path:
        base = root if root is not None else _ROOT
        return Path(base, self.trace_relpath)

    def config_path(self, root: Optional[Path] = None) -> Path:
        base = root if root is not None else _ROOT
        return Path(base, self.config_relpath)

    def accuracy_summary_path(self, root: Optional[Path] = None) -> Optional[Path]:
        if self.accuracy_summary_relpath is None:
            return None
        base = root if root is not None else _ROOT
        return Path(base, self.accuracy_summary_relpath)

    def as_dict(self) -> Mapping[str, object]:
        """Return a JSON-friendly snapshot of the workload metadata."""

        payload: Dict[str, object] = {
            "workload_id": self.workload_id,
            "plan_path": self.plan_relpath,
            "trace_path": self.trace_relpath,
            "config_path": self.config_relpath,
            "description": self.description,
            "tags": list(self.tags),
        }
        if self.accuracy_summary_relpath is not None:
            payload["accuracy_summary"] = self.accuracy_summary_relpath
        return payload


def _build_manifest() -> Dict[str, GoldenWorkload]:
    return {
        "cq_dma_roundtrip": GoldenWorkload(
            workload_id="cq_dma_roundtrip",
            plan_relpath="plans/cq_dma_roundtrip.yaml",
            trace_relpath="traces/cq_dma_roundtrip.jsonl",
            config_relpath="configs/cq_dma_roundtrip.json",
            description="Single-tile DMA roundtrip exercising dram↔spm flow.",
            accuracy_summary_relpath="summaries/cq_dma_roundtrip.json",
            tags=("dma", "sanity"),
        ),
        "cq_dma_chain": GoldenWorkload(
            workload_id="cq_dma_chain",
            plan_relpath="plans/cq_dma_chain.yaml",
            trace_relpath="traces/cq_dma_chain.jsonl",
            config_relpath="configs/cq_dma_chain.json",
            description="Three-stage DMA chain with dependency enforcement.",
            accuracy_summary_relpath="summaries/cq_dma_chain.json",
            tags=("dma", "dependency"),
        ),
        "cq_gemm_single": GoldenWorkload(
            workload_id="cq_gemm_single",
            plan_relpath="plans/cq_gemm_single.yaml",
            trace_relpath="traces/cq_gemm_single.jsonl",
            config_relpath="configs/cq_gemm_single.json",
            description="Baseline GEMM fed by DMA-loaded tiles with fence/flush.",
            accuracy_summary_relpath="summaries/cq_gemm_single.json",
            tags=("gemm", "baseline"),
        ),
        "cq_gemm_pipeline": GoldenWorkload(
            workload_id="cq_gemm_pipeline",
            plan_relpath="plans/cq_gemm_pipeline.yaml",
            trace_relpath="traces/cq_gemm_pipeline.jsonl",
            config_relpath="configs/cq_gemm_pipeline.json",
            description="Two-stage GEMM pipeline reusing intermediate outputs.",
            accuracy_summary_relpath="summaries/cq_gemm_pipeline.json",
            tags=("gemm", "pipeline"),
        ),
        "cq_mixed_latency": GoldenWorkload(
            workload_id="cq_mixed_latency",
            plan_relpath="plans/cq_mixed_latency.yaml",
            trace_relpath="traces/cq_mixed_latency.jsonl",
            config_relpath="configs/cq_mixed_latency.json",
            description="Mixed DMA/GEMM sequence with stride stressors.",
            accuracy_summary_relpath="summaries/cq_mixed_latency.json",
            tags=("dma", "gemm", "latency"),
        ),
    }


GOLDEN_WORKLOADS: Mapping[str, GoldenWorkload] = _build_manifest()


def iter_workloads() -> Iterator[GoldenWorkload]:
    """Yield the known workloads in deterministic order."""

    for key in sorted(GOLDEN_WORKLOADS.keys()):
        yield GOLDEN_WORKLOADS[key]


__all__ = ["GOLDEN_WORKLOADS", "GoldenWorkload", "iter_workloads"]
