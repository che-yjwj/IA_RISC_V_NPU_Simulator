# Tasks: IA-based RISC-V+NPU Simulator

**Input**: Design documents from `/specs/001-ia-risc-v/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/

## Phase 1: Foundation Engine (Weeks 1-4)

### Week 1: Project Setup & Core Engine
- [x] T001: [P] Set up Python project with `pytest`, `numpy`, `numba`, and `asyncio`.
- [x] T002: [P] Configure linting (e.g., ruff) and formatting (e.g., black).
- [x] T003: Implement the basic `RISCVEngine` class structure in `src/risc_v/engine.py`.
- [x] T004: Implement the `TimingHookSystem` class in `src/simulator/hooks.py`.
- [x] T005: Create a fixed lookup table for instruction latencies in `src/simulator/latency.py`.

### Week 2: ALU & Initial Testing
- [x] T006: [P] Implement basic ALU instructions (ADD, SUB, AND, OR, XOR) in `src/risc_v/instructions/alu.py`.
- [x] T007: [P] Write unit tests for the ALU instructions in `tests/unit/risc_v/instructions/test_alu.py`.
- [x] T008: Implement statistics collection for timing hooks in `src/simulator/hooks.py`.
- [x] T009: [P] Write integration tests for the basic simulation loop in `tests/integration/test_simulation.py`.

### Week 3: Memory System
- [x] T010: Implement memory access instructions (LD, SD, LW, SW) in `src/risc_v/instructions/memory.py`.
- [x] T011: [P] Write unit tests for memory access instructions in `tests/unit/risc_v/instructions/test_memory.py`.
- [x] T012: Implement memory access hooks in `src/simulator/hooks.py`.

### Week 4: Control Flow & Performance
- [x] T013: Implement branch instructions (BEQ, BNE, JAL, JALR) in `src/risc_v/instructions/control_flow.py`.
- [x] T014: [P] Write unit tests for branch instructions in `tests/unit/risc_v/instructions/test_control_flow.py`.
- [x] T015: [P] Set up performance benchmarks using `pytest-benchmark` in `tests/performance/test_performance.py`.

## Phase 2: NPU & Event System (Weeks 5-8)

### Week 5: NPU & Asyncio
- [x] T016: Implement the basic `NPU` model class in `src/npu/model.py`.
- [x] T017: Implement the MMIO interface for NPU communication in `src/simulator/mmio.py`.
- [x] T018: Set up the `asyncio` event loop in the main simulator class in `src/simulator/main.py`.

### Week 6: Adaptive Control
- [x] T019: Implement the fidelity level switching logic in `src/simulator/adaptive_controller.py`.
- [x] T020: Implement a simple classifier to detect when to switch between Lev0 and Lev1 in `src/simulator/classifier.py`.
- [x] T021: [P] Write tests for the adaptive controller in `tests/unit/test_adaptive_controller.py`.

### Week 7: Vector Operations & Bus
- [x] T022: Implement basic vector operations in the NPU model in src/npu/model.py.
- [x] T023: Implement the SPM (Scratchpad Memory) and Bus models in `src/simulator/memory.py`.

### Week 8: Optimization
- [ ] T024: Profile the simulator using `cProfile` and `line_profiler` to identify bottlenecks.
- [ ] T025: Apply `numba` and `numpy` optimizations to critical code paths.
- [ ] T026: [P] Run and analyze performance benchmarks.

## Phase 3: Integration & Validation (Weeks 9-12)

### Week 9: System Integration
- [ ] T027: Integrate the RISC-V engine, NPU, and memory system.
- [ ] T028: [P] Run end-to-end tests with simple workloads.

### Week 10: Memory Optimization & ROI
- [ ] T029: Optimize memory usage using techniques like object pooling.
- [ ] T030: Implement a more advanced ROI detection mechanism.

### Week 11: Workload Analysis
- [ ] T031: [P] Run the simulator with a variety of workloads (e.g., CNN layers).
- [ ] T032: Analyze the accuracy and performance of the simulator against the goals in `prd.md`.

### Week 12: Finalization
- [ ] T033: [P] Create final documentation for the simulator.
- [ ] T034: [P] Implement the CLI using the contract in `contracts/cli.md`.
- [ ] T035: [P] Run final benchmarks and generate a performance report.
- [x] T036: [P] Reorganize project documentation structure.
- [x] T037: [P] Create a comprehensive README.md file.
