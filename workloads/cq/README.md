# CQ Workloads (Experimental)

This directory stores sample Command Queue (CQ) traces that can be consumed by
the experimental `run-cq` CLI subcommand.

- `sample_gemm.jsonl` – A minimal load/compute/store sequence that demonstrates
  the JSONL schema (metadata header followed by command entries).

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

You can also run the queue through the simulator scaffold to obtain dispatcher
통계:

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
```

CQ ↔ ELF 비교 스텁으로 결과를 대비하려면:

```python
from pathlib import Path
from src.simulator.cq_runner import compare_cq_vs_elf

root = Path(".")
report = compare_cq_vs_elf(cq_trace=root / "workloads/cq/sample_gemm.jsonl")
print(report["status"], report["cq_summary"]["plan_summary"])
```
