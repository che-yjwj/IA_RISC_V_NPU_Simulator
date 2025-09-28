# Accuracy Guard Demonstration

This demo shows how to run the simulator with the accuracy guard enabled.

## Files

- `config.json` – turns on the guard and points to `golden_summary.json`.
- `golden_summary.json` – minimal set of stable metrics captured from `benchmark --instructions 1`.

## Usage

```bash
PYTHONPATH=ia_risc_v_npu \
python3 -m src.simulator.cli benchmark \
  --instructions 1 \
  --config workloads/demos/accuracy_guard/config.json \
  --output /tmp/accuracy_summary.json
```

The guard compares the generated summary with `golden_summary.json` and exits `0` when the deviations stay within the configured thresholds. To exercise the failure path, edit the golden file (for example, change `cycles` to `9999`) and rerun the command; the CLI will exit `1` and embed the comparison details under `accuracy_guard` in the output JSON.
