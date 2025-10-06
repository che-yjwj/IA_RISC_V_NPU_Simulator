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

## Regenerating the golden summary

1. `python -m scripts.regenerate_accuracy_golden`을 실행하면 골든 파일이 자동으로 갱신됩니다.
2. 수동으로 실행할 경우 `/tmp/accuracy_summary.json`에서 `accuracy_guard.status`가 `ok`인지 확인한 뒤 필요한 필드를 `configs/golden_summary.json`에 반영합니다. 분위수 값은 최대 4,096개의 표본을 근사한 결과이므로, 동일한 설정에서 재생성을 반복하면 허용 오차 내에서 일관된 값을 얻을 수 있습니다.
