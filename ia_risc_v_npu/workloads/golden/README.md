# CQ Golden Workloads

This directory seeds the Stage 7 backlog item **CQ-BG-006**.  It tracks the
canonical CQ workloads that will feed the accuracy guard and golden diff
automation once the trace pipeline is fully wired up.

## Contents

- `plans/` – YAML descriptions consumed by `src.cq.tools.plan_generator` to emit
  JSONL traces.
- `traces/` – materialised CQ JSONL traces generated from the plans.
- `configs/` – simulator config stubs with accuracy guard enabled (±5% 평균/단일 허용)
  pointing at the golden summaries for each workload.
- `summaries/` – placeholder accuracy guard outputs to be replaced with measured metrics.
- `manifest.py` – lightweight registry describing each workload, including the
  intended trace plan and the placeholder location for future accuracy guard
  summaries.

## Regeneration Workflow

1. Use `python -m src.cq.tools.plan_generator --input plans/<name>.yaml --output <path>.jsonl` to materialise a trace.
2. Feed the generated trace into `python -m src.simulator.cli run-cq` (optionally
   pre-loading tensors) to capture execution metrics.
3. Distill the relevant metrics into a golden summary JSON, update
   `summaries/`, and adjust thresholds if deviations exceed the ±5% defaults.
4. Run `python -m scripts.check_cq_accuracy` to ensure the accuracy guard passes
   for all registered workloads (ideal for CI integration).
