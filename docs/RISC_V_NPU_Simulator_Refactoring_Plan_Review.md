# RISC-V NPU Simulator Refactoring Plan Review

## Scope Of Review
- Document analysed: `docs/RISC_V_NPU_Simulator_Refactoring_Plan.md`
- Focus: feasibility of staged refactor, alignment with current code paths (`src/simulator`, `src/npu`, `src/risc_v`), immediate risks and follow-up actions.

## Plan Highlights
- Roadmap keeps the existing ELF → AdaptiveSimulator → CPU/NPU/Memory flow intact while addressing structural debts and unlocking future extensions.
- Key principles emphasise backwards-compatible CLI behaviour, JSON configs, and retention of tested modules such as `memory.py`, `accuracy.py`, and `npu/cluster.py`.
- Stage sequencing (baseline → config/CLI → scheduler → memory → CQ → docs) supports incremental delivery with regression coverage at every step.

## Codebase Snapshot
- `AdaptiveSimulator` in `src/simulator/main.py` wires bus, caches, DRAM, NPU cluster, MMIO, and event scheduling from validated JSON configs (`default_simulator_config`).
- Configuration validation (`src/simulator/config.py`) already compartmentalises per-section checks, making new schema fields straightforward to add.
- `NPUCluster` (`src/npu/cluster.py`) currently ships with min-finish-time and round-robin policies, deferred DMA handling, and utilisation/wait metrics.
- Event execution relies on the heap-based `EventScheduler` (`src/simulator/events.py`), providing a natural hook for future tracing and fidelity controls.
- CLI entry points (`src/simulator/cli.py`) expose `simulate` and `benchmark` subcommands with logging/trace options and have unit tests in `tests/unit/test_cli.py`.

## Feasibility Check
- **Stage 0**: Full unit/integration suites under `tests/` support capturing a reliable baseline and verifying deterministic snapshots.
- **Stage 1**: Config validator and CLI plumbing already exist; extending scheduler/logging options only requires threading new keys through `validate_simulator_config` to `AdaptiveSimulator`.
- **Stage 2**: `ClusterPolicy` enum and scheduling metrics ease incremental addition of policies (e.g. priority, weighted fairness) without disturbing DMA plumbing.
- **Stage 3**: Bus/DRAM parameters are centralised; enhancing logging or schema enforcement is practical but needs a closer pass through `MemorySystem` for detailed metrics.
- **Stage 4**: CQ pipeline has stubs only in documentation; new modules plus CLI feature flags will demand fresh schemas, adapters, and integration tests—the largest greenfield item.
- **Stage 5**: Summary/report generation already aggregates metrics, so expanding accuracy guards or documentation is low risk once earlier stages land.

## Immediate Next Steps
1. Execute `pytest tests/unit -vv` and targeted integration workloads to record the current behaviour snapshot before modifications.
2. Archive benchmark numbers via `python -m src.simulator.cli benchmark --instructions 200000` (default config) and store outcomes with timestamp in `docs/` or `specs/`.
3. Catalogue any external dependencies or optional packages (e.g. `pyelftools`) in `requirements.txt` notes to smooth Stage 0 environment validation.

