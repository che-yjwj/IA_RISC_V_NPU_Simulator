# Validation & Calibration Playbook

## 1. Regression Test Matrix
- **Fast unit sweep**: `pytest tests/unit -q` – use before every commit to catch logic regressions quickly.
- **Targeted integration**: `pytest tests/integration -q` – validates CPU↔NPU↔memory orchestration.
- **Full suite**: `pytest` – required before releases; includes performance/verification buckets.
- **Accuracy guard demo**: `python -m src.simulator.cli benchmark --instructions 1 --config ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json --output /tmp/accuracy_summary.json`
  - Fails fast if golden drift occurs; see `docs/accuracy_guard_ci.md` for CI guidance.

## 2. Benchmark Baselines
- **Throughput check**: `python -m src.simulator.cli benchmark --instructions 200000 --config <config.json>`
  - Capture `mips` and `elapsed_seconds`; compare with targets in `benchmark_snapshot.txt`.
- **Policy sweep**: use `ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json` and `ia_risc_v_npu/workloads/calibration/configs/priority_tuning.json` as starting points to compare scheduling impact.
- **Result logging**: store raw JSON summaries under `performance_results.json` (append or versioned snapshots).

## 3. Accuracy Guard Maintenance
- Regenerate demo goldens with `python -m scripts.regenerate_accuracy_golden --instructions 1`.
- For workload-specific goldens, reuse the script with `--config`/`--golds` overrides.
- Document every golden update alongside the deviation reason in change logs.

## 4. Calibration Workflow
1. **Establish baseline** using commands above; archive the JSON summaries.
2. **Tune parameters** (cache, DRAM, scheduler) via config files under `workloads/`.
3. **Re-run targeted tests** (unit/integration + benchmark) to isolate effects.
4. **Update goldens** when deviations are intentional and within defined tolerances.
5. **Record findings** in `docs/npu_scheduler_followup.md` or a new calibration note.

## 5. Automation Hooks
- Add the benchmark + accuracy guard commands to CI (GitHub Actions example in `docs/accuracy_guard_ci.md`).
- Consider scripting a consolidated run via `scripts/run_validation_suite.py` (see tooling checklist below).
- Nightly jobs can iterate over configuration matrices and aggregate stats into JSONL for trend analysis.

## 6. Tooling Checklist
- [ ] Integrate `python -m scripts.regenerate_accuracy_golden` into release workflow.
- [ ] Provide optional `scripts/run_validation_suite.py` to orchestrate tests (TBD).
- [ ] Maintain baseline artifacts (`benchmark_snapshot.txt`, `performance_results.json`).

> 최신 지표 정의: `docs/accuracy_guard_metrics.md`
> CI/자동화 가이드: `docs/accuracy_guard_ci.md`
