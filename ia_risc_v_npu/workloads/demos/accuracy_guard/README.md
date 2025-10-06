# Accuracy Guard Demonstration

This demo shows how to run the simulator with the accuracy guard enabled.

## Files

- `configs/baseline.json` – turns on the guard and points to `configs/golden_summary.json`.
- `configs/golden_summary.json` – minimal set of stable metrics captured from `benchmark --instructions 1`.

## Usage

```bash
python3 -m src.simulator.cli benchmark \
  --instructions 1 \
  --config workloads/demos/accuracy_guard/configs/baseline.json \
  --output /tmp/accuracy_summary.json
```

The guard compares the generated summary with `configs/golden_summary.json` and exits `0` when the deviations stay within the configured thresholds. Golden data now includes CPU/NPU 활용도(`cpu_metrics.utilization`, `npu_metrics.utilization`), 대기 지표(`wait_metrics.*`), 그리고 명령 페치 지연 분위수(`fetch_metrics.latency_p90`, `fetch_metrics.latency_p99`).

To exercise the failure path, edit the golden file (for example, change `cycles` to `9999` or bump one of the latency percentiles) and rerun the command; the CLI will exit `1` and embed the comparison details under `accuracy_guard` in the output JSON.
