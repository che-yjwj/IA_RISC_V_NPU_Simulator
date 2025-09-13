# Data Model for IA-based RISC-V+NPU Simulator

This document defines the key data entities for the simulator.

## RISC-V Core

Represents the state of the RISC-V processor.

**Attributes**:
- `registers`: An array of 32 general-purpose registers.
- `pc`: The program counter.
- `state`: The current state of the processor (e.g., fetching, decoding, executing).

## NPU

Represents the state of the Neural Processing Unit.

**Attributes**:
- `internal_registers`: Registers specific to the NPU.
- `execution_status`: The current status of the NPU (e.g., idle, running, stalled).

## Bus

Represents the communication channel between the RISC-V Core and the NPU.

**Attributes**:
- `pending_requests`: A queue of requests waiting for bus access.
- `status`: The current status of the bus (e.g., busy, idle).

## Memory

Represents the hierarchical memory system.

**Attributes**:
- `caches`: A list of cache levels.
- `main_memory`: The main memory.

## Event

Represents an action or occurrence within the NPU or bus.

**Attributes**:
- `type`: The type of event (e.g., memory access, NPU operation).
- `timestamp`: The simulation time at which the event occurs.
- `data`: Data associated with the event.

## Timing Hook

A mechanism to allow external code to be executed at specific points in the simulation time.

**Attributes**:
- `type`: The type of hook (e.g., fetch, decode, execute).
- `callback`: The function to call when the hook is triggered.
