# IA-RISC-V-NPU-Simulator

An IA-based Adaptive Simulator for RISC-V and NPU Hybrid Systems.

## 1. Project Overview

This project aims to develop a high-performance, adaptive simulator for a hybrid RISC-V CPU and NPU architecture. The primary goal is to overcome the speed limitations of traditional cycle-accurate simulators by employing a multi-level simulation approach.

The target is to achieve a simulation speed of 12-20 MIPS with an accuracy of ±15% compared to cycle-accurate models, representing a 50-200x performance improvement.

## 2. Key Features

-   **RISC-V IA Engine**: A functional instruction-accurate model of the RV64I instruction set.
-   **Deterministic Event Pipeline**: Instruction fetch, cache hierarchy, DRAM, and bus arbitration are modeled through the unified event scheduler—no legacy timing hooks remain.
-   **NPU Model**: Includes models for GEMM (General Matrix Multiply), vector units, and local memory (SPM).
-   **Adaptive Fidelity Control**: A controller that dynamically switches between simulation fidelity modes based on instruction complexity and execution context to balance speed and accuracy.

## 3. System Architecture

The simulator is composed of three main layers:

1.  **CLI & Configuration**: Manages simulation setup, program loading, and result reporting.
2.  **Adaptive Simulator Core**: The heart of the simulator, featuring the RISC-V IA engine, an `asyncio`-based event manager, and the adaptive fidelity controller.
3.  **Hardware Models**: Abstract models for the NPU, memory system, and bus interconnects.

The adaptive core now relies entirely on the discrete event scheduler. Instruction fetch, cache fills, and DRAM latencies are resolved through the shared memory subsystem so that repeat runs produce identical timelines.

## 4. Getting Started

### Prerequisites

-   Python 3.10+
-   `pip` for package management

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/IA_RISC_V_NPU_Simulator.git
    cd IA_RISC_V_NPU_Simulator
    ```

2.  **Create and activate an isolated environment (recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the simulator in editable mode:**
    ```bash
    python3 -m pip install -e ia_risc_v_npu[dev]
    ```

    This command exposes the `src/` packages (`npu`, `risc_v`, `simulator`), the
    `workloads` generators, and the helper scripts without requiring manual
    `PYTHONPATH` exports. The optional `[dev]` extra brings in the pytest stack
    used by the repository.

### Running the Simulator

Use the CLI entry point to execute an ELF workload. The generated summary JSON now includes cache/bus/memory/NPU utilization metrics alongside cycles, instructions, and MIPS so you can compare runs and diagnose bottlenecks.

```bash
python -m src.simulator.cli simulate build/program.elf --config configs/example.json --output results/summary.json
```

*Note: The simulator expects a RISC-V ELF binary; configuration is optional but accepted via `--config`.*

### Configuring Hardware Profiles

Hardware knobs are controlled through the JSON configuration passed via `--config`. Baseline profiles live alongside their workloads under `workloads/<scenario>/configs/` (see `ia_risc_v_npu/docs/reference_configs.md` for a catalog). A minimal example adjusts cache sizes, bus bandwidth, DRAM timings, and the NPU policy without touching Python code:

```json
{
  "cache": {
    "l1": {"size_bytes": 16384, "hit_latency": 6},
    "l2": {"associativity": 16}
  },
  "bus": {"slice_bytes": 48, "bandwidth_bytes_per_cycle": 24},
  "dram": {"t_cas": 18},
  "npu": {"cores": 3, "policy": "rr"},
  "determinism": {"seed": 123, "blas_threads": 4}
}
```

All unspecified fields fall back to the defaults documented in `src/simulator/config.py`.

### Deterministic Environment

Use the deterministic helper to pin BLAS threads and RNG seeds before running tooling. A regression test (`tests/integration/test_deterministic_simulation.py`) hashes two simulation runs to guarantee identical timelines for identical inputs.

```bash
python -m scripts.deterministic_env -- python -m pytest -q
```

Pass `--repeat 3 --verify` to execute a command multiple times and assert the captured output remains identical, which is helpful when checking CI or benchmark determinism.

### Measuring Performance (T032)

Benchmark wall-clock throughput and capture MIPS metrics. Optionally gate the run with explicit minimum/maximum thresholds.

```bash
python -m src.simulator.cli benchmark --instructions 200000 --min-mips 0.05 --max-mips 0.10 --output results/benchmark.json
```

The written JSON includes executed instruction count, elapsed seconds, calculated MIPS, and the `mips_guard` section documenting whether the run stayed within the configured bounds (adjust the thresholds to match your calibrated baseline or target window).

For CI smoke testing or quick local checks, reduce the workload to keep runtime
lightweight:

```bash
python3 -m src.simulator.cli benchmark --instructions 1000
```

### Reporting & Accuracy Guard

- Simulation summaries expose extended metrics: per-level cache hit/miss counts, average memory access latency (AMAT), bus transaction latency, fetch miss rates, stall breakdown, and NPU utilization. These fields are available both in CLI output and the optional `--output` JSON via `prepare_summary`.
- Optional accuracy guard support validates the summary against a golden JSON snapshot before exiting. Configure it via the `accuracy_guard` block in the simulator config; exceeding the allowed deviation returns a non-zero exit code and embeds comparison details in the summary.
- A runnable example lives in `ia_risc_v_npu/workloads/demos/accuracy_guard/` with a ready-to-use config, golden metrics, and README walkthrough.

## 5. Technology Stack

-   **Core Language**: Python
-   **Concurrency**: `asyncio` for event-based simulation
-   **Performance**: `NumPy` and `Numba` for accelerating numerical computations
-   **Testing**: `pytest` and `pytest-benchmark`

## 6. Development Roadmap

The project follows a 12-week development plan, divided into three main phases:

-   **Phase 1 (Weeks 1-4)**: Foundational engine, including the RISC-V IA core and basic timing hooks.
-   **Phase 2 (Weeks 5-8)**: NPU modeling, event system implementation, and adaptive control logic.
-   **Phase 3 (Weeks 9-12)**: System integration, workload testing, and performance optimization.

For a detailed breakdown, please refer to the `docs/prd.md` file.
