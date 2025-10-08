# CQ Workloads (Experimental)

This directory stores sample Command Queue (CQ) traces that can be consumed by
the experimental `run-cq` CLI subcommand.

- `sample_gemm.jsonl` – A minimal load/compute/store sequence that demonstrates
  the JSONL schema (metadata header followed by command entries).
- `multi_tile_gemm.jsonl` – Two GEMM tiles with repeated DMA/FENCE steps that
  accumulate into a shared output buffer.
- `sample_conv.yaml/jsonl` – Conv→GEMM lowering example with explicit DMA load/store,
  GEMM compute, and an SPM fence to flush the tile.

Validate a trace with:

```bash
python -m src.simulator.cli run-cq workloads/cq/sample_gemm.jsonl --verbose
```

The validator cross-checks opcodes against the baseline ISA spec (`specs/isa.yaml`)
unless `--skip-isa-check` is provided.

Once validated you can derive a structured execution plan via:

```python
from src.cq import build_execution_plan, load_cq_trace, load_isa_spec

queue = load_cq_trace("workloads/cq/sample_gemm.jsonl")
spec = load_isa_spec()
plan = build_execution_plan(queue, spec)
print(plan.summary())
```

`CQDispatcher`는 시뮬레이터 스캐폴드를 통해 커맨드 큐(CQ)를 실행하는 핵심 요소입니다. 이 디스패처는 `AdaptiveSimulator.run_cq_trace`와 동일한 자원 스케줄링 파이프라인을 사용하여 명령을 직접 스트리밍하므로, CLI에서 얻는 결과와 동일한 정확한 시뮬레이션 결과를 제공합니다. 이를 통해 DMA, 버스, TE(Tensor Engine), SPM(Scratchpad Memory) 등 자원 모델의 동작을 일관되게 반영할 수 있습니다.

Simulate the trace directly and capture dispatcher/lane metrics with:

```bash
python -m src.simulator.cli run-cq workloads/cq/sample_gemm.jsonl \
  --simulate \
  --cq-policy rr \
  --cq-lane-limit dma=2 \
  --output /tmp/cq_simulated.json
```

`summary["cq_execution"]["dispatch"]["lane_usage"]`에는 레인별 누적 처리량과
최대 동시 실행 수가 기록됩니다. Accuracy Guard 골든 리포트도 동일한 지표를
사용하므로, 정책이나 용량을 바꿀 때 ±5% 편차로 회귀를 감시할 수 있습니다.

Python API로 직접 실행할 수도 있습니다. 이 경우 `run_cq_trace`가 반환한
요약은 CLI와 동일한 구조를 따릅니다.

```python
import numpy as np

from src.simulator.main import AdaptiveSimulator

sim = AdaptiveSimulator()
sim.load_cq_tensors(
    {
        "dram://inputs": {"shape": [2, 2], "values": [1.0, 2.0, 3.0, 4.0]},
        "dram://weights": np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
    }
)
summary = sim.run_cq_trace(queue)
print(summary["dispatch"]["queue_wait"])
print(summary["dispatch"]["lane_usage"])
print(summary["execution"]["count"])  # DMA/GEMM/FENCE counts recorded by dispatcher
print(summary["cq_execution"]["dispatch"]["lane_usage"])  # identical to CLI simulate mode

# Multi-tile example: aligns with tests/integration/test_cq_dispatcher.py::test_cq_multi_gemm_with_repeated_fence
queue_mt = load_cq_trace("workloads/cq/multi_tile_gemm.jsonl")
mt_summary = sim.run_cq_trace(queue_mt)
print(mt_summary["execution"]["count"])  # {'dma': 5, 'gemm': 2, 'fence': 2}
```

CQ ↔ ELF 비교 스텁으로 결과를 대비하려면:

```python
from pathlib import Path
from src.simulator.cq_runner import compare_cq_vs_elf

root = Path(".")
report = compare_cq_vs_elf(cq_trace=root / "workloads/cq/sample_gemm.jsonl")
print(report["status"], report["cq_summary"]["plan_summary"])
print(report["cq_summary"]["dispatch"]["executed"])

# Dispatcher metrics with the extended CQ sample
report_mt = compare_cq_vs_elf(cq_trace=root / "workloads/cq/multi_tile_gemm.jsonl")
print(report_mt["cq_summary"]["dispatch"]["lane_usage"])
print(report_mt["cq_summary"]["execution"]["count"])
```

`compare_cq_vs_elf` internally calls `AdaptiveSimulator.run_cq_trace`, so the
CQ summary in the report is generated via the same dispatcher-driven execution
path as the CLI.
