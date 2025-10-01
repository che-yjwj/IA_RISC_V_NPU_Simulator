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
- Tune the CNN integration workload size when triaging resource usage:
  ```bash
  CNN_TEST_PAYLOAD_SCALE=0.1 python3 -m pytest \
      tests/integration/test_multilayer_cnn.py -q
  ```
  Alternatively, pass `--cnn-payload-scale` to override the default 0.05 ratio.
- Capture per-phase peak memory when diagnosing OOM risk:
  ```bash
  python3 -m pytest tests/integration/test_multilayer_cnn.py -q \
      --cnn-memory-trace
  ```
  Enable richer allocation traces with `CNN_MEMORY_TRACE=1` (or the flag above),
  adjust the stack depth via `CNN_MEMORY_TRACE_FRAMES`, and control the number
  of reported hot spots with `CNN_MEMORY_TRACE_TOP`.
- Override hardware profiles by editing the JSON passed to `--config`:
  ```json
  {
    "cache": {"l1": {"size_bytes": 16384}},
    "bus": {"grant_latency": 2},
    "dram": {"t_cas": 18},
    "npu": {"cores": 4, "policy": "rr"}
  }
  ```
  Each field is validated via `src.simulator.config.validate_simulator_config`, so invalid values raise actionable errors.
- 참고용 기본 프로필은 `workloads/demos/cnn/configs/integration.json`에 있으며, CNN 통합 테스트 및 벤치마크 연습에 그대로 사용할 수 있습니다. 추가 베이스라인 목록과 세부 설명은 `docs/reference_configs.md`에서 확인하세요.
- Quick performance smoke test (keeps workloads small for CI):
  ```bash
  python3 -m src.simulator.cli benchmark --instructions 1000
  ```
- Simulation entry point with explicit config:
  ```bash
  python3 -m src.simulator.cli simulate workloads/demos/example/program.elf \
      --config workloads/demos/example/configs/default.json
  ```
- Adjust logging without editing code by combining `--log-level` and
  component traces. For example, keep global INFO logs but capture bus activity:
  ```bash
  python3 -m src.simulator.cli simulate workloads/demos/example/program.elf \
      --config workloads/demos/example/configs/default.json \
      --log-level INFO --trace bus
  ```
  Use `--trace memory` or `--trace npu` (repeatable) for other components, or
  bump the base verbosity to DEBUG for all simulator logs.

## Workflow Notes

- After activating the virtual environment, keep `python3`/`pip` prefixes to
  avoid system-wide installs.
- Regenerate workloads through the scripts in `workloads/` to preserve
  reproducibility; avoid committing large binaries.
- CI jobs assume editable installs: verify new tooling by running the
  `python3 -m pip install -e ia_risc_v_npu[dev]` command locally before pushing.
- The CI pipeline runs a smoke check (`python3 -m pytest tests/unit -vv`) right
  after the editable install; mirror this locally to catch import regressions
  early.
- 버스 마스터 ID와 주요 메모리 맵 주소는 `src.simulator.identifiers`에 정리되어 있으니, 새 코드나
  테스트에서는 해당 enum/상수를 재사용해 매직 넘버 확산을 방지하세요.
