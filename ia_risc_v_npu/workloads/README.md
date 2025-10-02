# Workload Assets Guide

The `workloads/` package hosts reproducible generators, demo configurations, and
profiling utilities used across the simulator tests and documentation. Generated
artifacts stay out of version control; use the helper scripts to recreate them
on demand.

## Directory Overview

- `demos/` – reference workloads paired with ready-to-run JSON configs.
- `generators/` – deterministic asset builders.
- `generated/` – default drop location for regenerated tensors and programs
  (ignored by git).
- `profiling/` – utilities for collecting trace data during performance
  experiments.

## Two-Layer CNN Assets

Use the generator below to reproduce the tensors and instruction stream consumed
by `tests/integration/test_multilayer_cnn.py` and the CNN demo configs:

```bash
python3 -m workloads.generators.generate_two_layer_cnn_assets \
  --output-dir workloads/generated/two_layer_cnn \
  --payload-scale 0.05
```

The command emits:

- `input.npy` – 1×5×5 activation tensor (`uint32`).
- `layer1_weights.npy` – first-layer kernels shaped 2×1×3×3.
- `layer2_weights.npy` – second-layer kernels shaped 3×2×2×2.
- `program.npy` – concatenated synthetic NOP payload followed by the halt
  instruction.
- `metadata.json` – shapes, payload scale, and bookkeeping data.

All arrays are seeded with `np.arange` to keep results deterministic. Adjust the
`--payload-scale` flag when you want to stress-test longer synthetic programs.
Add `--force` to overwrite an existing output directory, and pass `--dtype` to
experiment with alternative integer widths.

## Regeneration Checklist

1. Create or update your virtual environment and install the project in editable
   mode (`python3 -m pip install -e ia_risc_v_npu[dev]`).
2. Regenerate the required assets with the appropriate script from
   `workloads/generators/`.
3. Store the outputs under `workloads/generated/` (or another ignored
   directory). Avoid committing these binaries—record only the script changes
   and supporting configs.
4. Document any new generator or usage flow in this README so other contributors
   can reproduce identical tensors.
