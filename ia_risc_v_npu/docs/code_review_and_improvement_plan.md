# Code Review & Improvement Plan

## 1. Introduction

This document outlines key recommendations for improving the RISC-V NPU simulator codebase. The current architecture is well-designed, featuring a clear separation of concerns and a sophisticated hybrid simulation model. The following suggestions aim to enhance the project's robustness, maintainability, and ease of use for future development and experimentation.

## 2. Recommendations

### 2.1. Test Environment Restoration and Enhancement (Priority: Critical)

**Observations**
- Running `pytest ia_risc_v_npu/tests/unit -q` currently fails with `ModuleNotFoundError: No module named 'src'` because the simulator packages are not installable and the runner cannot resolve `src.*` or `scripts.*`.
- Integration workloads such as `ia_risc_v_npu/tests/integration/test_multilayer_cnn.py` allocate sizeable tensors and previously exhausted CI memory budgets.

**Checklist**
- [x] Extend `ia_risc_v_npu/pyproject.toml` with `[build-system]`/`[project]` metadata so the repository can be installed in editable mode.
- [x] Document the editable install flow (`pip install -e ia_risc_v_npu`) in `README.md` and `docs/development.md` so contributors drop the `PYTHONPATH` export.
- [x] Add explicit `__init__.py` files under `ia_risc_v_npu/src/`, `ia_risc_v_npu/src/npu/`, `ia_risc_v_npu/src/risc_v/`, `ia_risc_v_npu/src/simulator/`, and any other package directories that pytest imports.
- [x] Remove the `pythonpath = ia_risc_v_npu` override from `pytest.ini` once packaging is in place.
- [x] Add a pre-commit or CI smoke command that runs `pytest tests/unit -vv` after performing the editable install to catch path regressions early.
- [ ] Measure peak memory usage of `tests/integration/test_multilayer_cnn.py` (and similar cases) to identify the sections that trigger OOM.
- [x] Extract large tensor preparation into reusable fixtures or synthetic stubs so unit tests validate behavior without materializing full workloads.
- [x] Retain a single high-level integration run with reduced tensor sizes to keep golden coverage while staying inside CI resource limits.

### 2.2. Centralized Configuration Management (Priority: High)

**Observations**
- `src/simulator/cli.py` validates JSON configs, yet `src/simulator/main.py` still constructs the bus, caches, DRAM, and NPU with hard-coded defaults, so runtime tuning has no effect.
- Workloads in `workloads/` must patch sources to explore new hardware permutations, slowing iteration.

**Checklist**
- [x] Update `AdaptiveSimulator.__init__` to accept a `config: dict` parameter produced by `validate_simulator_config`.
- [x] Refactor simulator setup to read bus/cache/DRAM/SPM/NPU parameters from the supplied config instead of the current module constants.
- [x] Ensure deterministic options (`seed`, BLAS threads) are applied before component construction, matching the config values.
- [x] Pass the loaded config from `run_simulate` and `run_benchmark` into `AdaptiveSimulator`, including honoring `max_cycles` overrides.
- [x] Extend `tests/unit/simulator/test_config_validation.py` with assertions that edited config knobs alter instantiated component attributes.
- [x] Add new unit coverage for `AdaptiveSimulator` verifying cache/bus parameters change when the config values change.
- [ ] Publish reference JSON configs under `workloads/<scenario>/configs/` and annotate their usage in the workload README files.
- [x] Add documentation to `docs/` describing how to swap hardware profiles via the CLI without modifying Python modules.

### 2.3. Refactor "Magic Numbers" (Priority: Medium)

**Observations**
- Identifiers such as `CPU_MASTER_ID = 0`, `NPU_DMA_MASTER_ID = 1`, and memory-map constants in `src/simulator/main.py` leak throughout the code and tests, making refactors risky.
- Similar literals appear in bus metrics and event scheduler tests, duplicating intent.

**Checklist**
- [ ] Create a shared `src/simulator/identifiers.py` (or similar) that defines enums for bus masters, address ranges, and memory-mapped devices.
- [ ] Replace raw literals such as `CPU_MASTER_ID = 0` and `DRAM_BASE = 0x0` in `AdaptiveSimulator` with references to the new enums/constants.
- [ ] Update `Bus` and `NPUCluster` constructors to take enum values (with backward-compatible fallbacks) and adjust call sites accordingly.
- [ ] Migrate unit tests to compare against enum members (`BusMasterID.CPU`) in assertions and fixtures.
- [ ] Add regression tests that fail if mismatched enum values are provided, guaranteeing future contributors keep identifiers aligned.
- [ ] Document the enums in developer docs so new modules extend the shared identifiers rather than inventing new magic numbers.

### 2.4. Enhanced Logging for Debugging (Priority: Low)

**Observations**
- `Bus` exposes metrics but publishes almost no runtime logging, and `NPUCluster`/`MemorySystem` operate silently, hindering async debugging.
- Developers currently instrument ad-hoc prints when triaging pipeline stalls or cache issues.

**Checklist**
- [ ] Add structured `LOGGER.debug` calls inside `Bus.request`, `_schedule`, and `sync_time` to trace grant/complete timings and queue depth.
- [ ] Instrument `NPUCluster.submit`, `flush_deferred_dma`, and `metrics` to emit task-level lifecycle events when debug logging is enabled.
- [ ] Extend cache miss handling in `MemorySystem` to log evictions, write-backs, and latency contributions at `DEBUG` level.
- [ ] Modify `AdaptiveSimulator` to accept optional logger instances (or a factory) and propagate them to bus/NPU/memory components.
- [ ] Introduce a CLI flag (e.g., `--log-level`, `--trace-bus`) that toggles the detailed logging without editing code.
- [ ] Update developer docs with sample logging configurations and snippets showing how to enable targeted tracing during performance triage.

### 2.5. Development Workflow & CI Hygiene (Priority: Medium)

**Observations**
- Tests import modules directly from `scripts/`, but packaging metadata is not yet defined, and developer docs describe `python` rather than `python3` entry points.
- Tooling hooks (black/ruff) are configured but not enforced in CI or contributor guidance, and benchmark runs are manual.
- Workload assets are generated ad-hoc, risking drift between developers.

**Checklist**
- [x] Ensure the new packaging metadata includes the `scripts` package so `tests/unit/test_deterministic_env_script.py` passes after installation.
- [x] Update onboarding docs (`README.md`, `docs/development.md`) with the editable install workflow, explicit `python3` usage, and common CLI/test commands.
- [ ] Add CI or pre-commit jobs to run `black --check` and `ruff`, aligning with the existing `pyproject.toml` configuration.
- [x] Document a lightweight benchmark smoke test (e.g., `python -m src.simulator.cli benchmark --instructions 1000`) and consider wiring it as an optional CI stage to catch major regressions.
- [ ] Provide deterministic workload generation scripts under `workloads/` along with instructions for regenerating large tensors to keep version control lean.
