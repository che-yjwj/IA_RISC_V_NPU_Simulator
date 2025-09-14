# IA-RISC-V-NPU-Simulator

An IA-based Adaptive Simulator for RISC-V and NPU Hybrid Systems.

## 1. Project Overview

This project aims to develop a high-performance, adaptive simulator for a hybrid RISC-V CPU and NPU architecture. The primary goal is to overcome the speed limitations of traditional cycle-accurate simulators by employing a multi-level simulation approach.

The target is to achieve a simulation speed of 12-20 MIPS with an accuracy of ±15% compared to cycle-accurate models, representing a 50-200x performance improvement.

## 2. Key Features

-   **RISC-V IA Engine**: A functional instruction-accurate model of the RV64I instruction set.
-   **2-Level Adaptive Simulation**:
    -   **Level 0 (Fast Mode)**: Utilizes timing hooks and statistical models for high-speed simulation (15-20 MIPS).
    -   **Level 1 (Accurate Mode)**: Employs a detailed, event-based simulation for high-accuracy analysis of specific regions of interest (3-8 MIPS).
-   **NPU Model**: Includes models for GEMM (General Matrix Multiply), vector units, and local memory (SPM).
-   **Adaptive Fidelity Control**: A controller that dynamically switches between simulation levels based on instruction complexity and execution context to balance speed and accuracy.

## 3. System Architecture

The simulator is composed of three main layers:

1.  **CLI & Configuration**: Manages simulation setup, program loading, and result reporting.
2.  **Adaptive Simulator Core**: The heart of the simulator, featuring the RISC-V IA engine, an `asyncio`-based event manager, and the adaptive fidelity controller.
3.  **Hardware Models**: Abstract models for the NPU, memory system, and bus interconnects.

The adaptive core uses a combination of timing hooks for fast, high-level latency estimation (Lev0) and a discrete event-based system for detailed, accurate simulation when required (Lev1).

## 4. Getting Started

### Prerequisites

-   Python 3.10+
-   `pip` for package management

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/IA_RISC_V_NPU_Simulator.git
    cd IA_RISC_V_NPU_Simulator/ia_risc_v_npu
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Simulator

The main entry point for the simulator is `src/simulator/main.py`.

```bash
python src/simulator/main.py
```

*Note: The simulator currently expects a `config.json` file in the execution directory.*

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
