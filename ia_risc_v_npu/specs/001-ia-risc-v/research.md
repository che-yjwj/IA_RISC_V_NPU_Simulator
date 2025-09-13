# Research for IA-based RISC-V+NPU Simulator

This document outlines the best practices for the core technologies used in the simulator.

## asyncio

**Decision**: Use a single, centralized event loop to manage all simulation events.

**Rationale**: A single event loop simplifies the management of simulation time and the synchronization of events between the RISC-V core, NPU, and bus. It provides a clear and predictable execution model.

**Alternatives considered**: Multiple event loops were considered but rejected due to the complexity of synchronization and the potential for race conditions.

**Best Practices**:
- Use `async def` for all simulation components that involve time-based events.
- Use `asyncio.Queue` for communication between components.
- Use `loop.call_later()` or a similar mechanism to schedule events at specific simulation times.

## NumPy

**Decision**: Use NumPy for all vector and matrix operations within the RISC-V core and NPU models.

**Rationale**: NumPy provides highly optimized and efficient data structures and operations for numerical computing, which is essential for achieving the performance goals of the simulator.

**Alternatives considered**: Standard Python lists and loops were considered but are too slow for the performance requirements.

**Best Practices**:
- Use NumPy arrays for all numerical data.
- Vectorize operations whenever possible to avoid explicit loops in Python.
- Use NumPy's data types to control memory usage.

## Numba

**Decision**: Use Numba's `@jit` decorator to JIT-compile performance-critical sections of the Python code, such as the main simulation loop and complex instruction decoding.

**Rationale**: Numba can significantly speed up Python code, often to near-C speeds, which is crucial for overcoming Python's performance limitations and meeting the MIPS target.

**Alternatives considered**: Cython was considered, but Numba is easier to use and requires less code modification.

**Best Practices**:
- Identify bottlenecks using profiling tools like `cProfile` and `line_profiler` before applying Numba.
- Use `nopython=True` mode for maximum performance.
- Avoid using Python features that are not supported by Numba in JIT-compiled functions.

## pytest

**Decision**: Use pytest for all unit, integration, and performance tests.

**Rationale**: pytest is a mature and feature-rich testing framework for Python that simplifies test writing and provides powerful features like fixtures and plugins.

**Alternatives considered**: Python's built-in `unittest` framework was considered, but pytest offers a more concise and flexible syntax.

**Best Practices**:
- Use fixtures to set up and tear down test environments.
- Use `pytest-benchmark` for performance testing and regression tracking.
- Organize tests into `unit`, `integration`, and `performance` subdirectories.
