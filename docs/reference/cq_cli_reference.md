# CQ CLI Reference (Stage 9 Draft)

## run-cq
- `--simulate` : execute CQ trace via simulator, emits `cq_execution` block with lane usage
  and `dispatch.timeline` for Gantt/CSV export.
- `--cq-policy`, `--cq-lane-limit` : override dispatcher policy and lane capacities
- Output JSON (simulate mode):
  - `cq_execution.dispatch.timeline` → per-command ticks (`cmd_id,start_tick,end_tick,lane`)
  - `cq_execution.config` → resolved dispatcher policy/lane limits for reproducibility
- TODO: Add detailed argument table and examples.

## check_cq_accuracy
- Lane usage metrics (`dispatch.lane_usage.*`) are now part of Accuracy Guard comparisons.
- Output schema: see `scripts/check_cq_accuracy`.

## Utility Scripts
- `python -m src.scripts.generate_isa_cq_reference` → refreshes `docs/reference/isa_cq_reference.md`
- `python -m src.scripts.cq_timeline_export <summary.json> --output timeline.csv`
  → extracts dispatcher timeline for plotting notebooks.
