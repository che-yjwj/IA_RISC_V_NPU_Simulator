# Repository Guidelines

## Project Structure & Module Organization
The active code base resides in `ia_risc_v_npu/src`, with architecture-specific logic in `risc_v/`, accelerator models in `npu/`, and orchestration utilities in `simulator/`. Shared documents live in `docs/` and `specs/` (requirements, roadmap, performance notes). Scenario generators and reference inputs belong under `workloads/`. Tests mirror the runtime layout: `tests/unit` for pure functions, `tests/integration` for multi-component flows, `tests/performance` and `tests/verification` for benchmarking and golden-model checks. Keep new assets alongside the closest existing module to simplify discovery.

## Build, Test, and Development Commands
- `pip install -r ia_risc_v_npu/requirements.txt` installs the minimal dev stack.
- `python -m src.simulator.cli simulate <path/to/program.elf> --config <path/to/config.json>` runs an ELF workload; store configs next to the workload you are exercising.
- `python -m src.simulator.cli benchmark --instructions 200000` measures wall-clock throughput and reports MIPS so you can check the 12–20 MIPS target.
- `pytest` runs the entire suite; use `pytest tests/unit -vv` before opening reviews for faster iteration.
- `pytest tests/performance --benchmark-only` is reserved for profiling regressions; run it before merging any timing-sensitive change.

## Coding Style & Naming Conventions
Python code follows 4-space indentation, `black`/`ruff` with an 88 character line limit (`pyproject.toml`). Keep modules snake_case, classes PascalCase, async coroutines suffixed `_async` when disambiguation helps. Prefer type hints on public APIs and keep simulator hooks documented with short docstrings. Data files and workloads should use descriptive, kebab-cased filenames.

## Testing Guidelines
Add or update unit tests whenever you touch `src/`. Integration tests should cover cross-module behavior (e.g., simulator ↔ NPU handoff). Use `pytest.mark.asyncio` for coroutine tests and isolate slow cases with `@pytest.mark.performance`. Provide fixtures for any new sample programs, and refresh golden outputs under `tests/verification` when logic changes. Never skip performance tests if you modify latency models.

## Commit & Pull Request Guidelines
Commits follow Conventional Commits (`feat(simulator): ...`, `fix(riscv): ...`). Limit each commit to one logical change and ensure passing tests beforehand. PRs need a concise summary, links to roadmap tasks, and evidence for results: include benchmark diffs or console snippets when relevant. Tag reviewers familiar with the touched subsystem and note config requirements in the description.

## Configuration & Security Tips
Store experimental configs outside version control when possible; scrub secrets before sharing traces. The simulator reads JSON configs at runtime, so validate schema changes against existing workloads. Avoid committing large binary traces—reference them via reproducible scripts under `workloads/`.
