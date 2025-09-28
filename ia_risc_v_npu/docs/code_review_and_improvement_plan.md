# Code Review & Improvement Plan

## 1. Introduction

This document outlines key recommendations for improving the RISC-V NPU simulator codebase. The current architecture is well-designed, featuring a clear separation of concerns and a sophisticated hybrid simulation model. The following suggestions aim to enhance the project's robustness, maintainability, and ease of use for future development and experimentation.

## 2. Recommendations

### 2.1. Test Environment Restoration and Enhancement (Priority: Critical)

**Problem:**
The `pytest` test suite is currently non-functional due to `ModuleNotFoundError` errors, preventing any automated verification of code changes. Additionally, tests are being terminated by the OS's OOM (Out-Of-Memory) killer, suggesting they are too resource-intensive.

**Solution:**
1.  **Resolve `PYTHONPATH` Issue:** Implement a standard Python project setup to ensure tests can run without manual environment variable configuration. This can be achieved by:
    *   Configuring `pythonpaths` in the `pytest.ini` file.
    *   Structuring the project to be installable in "editable" mode (`pip install -e .`).
2.  **Refactor and Optimize Tests:**
    *   Break down large, resource-heavy integration tests into smaller, focused unit tests for each component (`NPUCluster`, `Bus`, `MemorySystem`, etc.).
    *   This will reduce the memory footprint of the test suite, prevent OOM errors, and allow for more precise identification of failures.

### 2.2. Centralized Configuration Management (Priority: High)

**Problem:**
Critical simulation parameters such as NPU core count, cache sizes, and memory timing values are hard-coded directly within the source code (e.g., in `src/simulator/main.py`). This makes it difficult to run different experiments without modifying the code.

**Solution:**
*   Externalize all simulation parameters into a dedicated configuration file (e.g., `config.yaml` or `config.json`).
*   The simulator should load this file at startup to configure its components. This will allow researchers and developers to easily define and switch between different hardware configurations and scenarios.

### 2.3. Refactor "Magic Numbers" (Priority: Medium)

**Problem:**
The code uses hard-coded integer literals ("magic numbers") to represent system-wide identifiers, such as `CPU_MASTER_ID = 0` and `NPU_DMA_MASTER_ID = 1`. This reduces readability and increases the risk of errors if these values need to be changed.

**Solution:**
*   Replace these magic numbers with a dedicated `Enum` (e.g., `MasterID`, `DeviceID`).
*   Using named identifiers like `MasterID.CPU` and `MasterID.NPU_DMA` will make the code more self-documenting and easier to maintain.

### 2.4. Enhanced Logging for Debugging (Priority: Low)

**Problem:**
The current level of logging is insufficient for debugging the complex, asynchronous interactions within the simulator. When unexpected behavior occurs, tracing the sequence of events can be challenging.

**Solution:**
*   Implement detailed, multi-level logging in key components:
    *   **Bus:** Log request queuing, granting, and completion.
    *   **NPUCluster:** Log task submission, DMA queue state changes, and `flush` events.
    *   **MemorySystem:** Log cache hits, misses, evictions, and write-backs.
*   Using different log levels (e.g., `DEBUG`, `INFO`) will allow for fine-grained control over the verbosity of the output during debugging.
