# Development Guide

## Environment Setup

- Ensure Python 3.10 or newer is installed (`python3 --version`).
- Create a virtual environment to keep simulator dependencies isolated:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- Install the simulator in editable mode so `src/` and `scripts/` resolve via
  standard imports:
  ```bash
  python3 -m pip install -e ia_risc_v_npu[dev]
  ```
  The optional `[dev]` extra installs the pytest tooling used in CI.

## Common Commands

- Run unit tests after the editable install to confirm imports:
  ```bash
  python3 -m pytest tests/unit -vv
  ```
- Execute the full suite before submitting changes:
  ```bash
  python3 -m pytest
  ```
- Quick performance smoke test (keeps workloads small for CI):
  ```bash
  python3 -m src.simulator.cli benchmark --instructions 1000
  ```
- Simulation entry point with explicit config:
  ```bash
  python3 -m src.simulator.cli simulate workloads/demos/example/program.elf \
      --config workloads/demos/example/configs/default.json
  ```

## Workflow Notes

- After activating the virtual environment, keep `python3`/`pip` prefixes to
  avoid system-wide installs.
- Regenerate workloads through the scripts in `workloads/` to preserve
  reproducibility; avoid committing large binaries.
- CI jobs assume editable installs: verify new tooling by running the
  `python3 -m pip install -e ia_risc_v_npu[dev]` command locally before pushing.
