# CLI Contract for IA-based RISC-V+NPU Simulator

This document defines the command-line interface for the simulator.

## `simulate` command

Runs the simulation.

**Usage**:
```
simulate [OPTIONS] <ELF_FILE>
```

**Arguments**:
- `<ELF_FILE>`: The path to the ELF file to be simulated.

**Options**:
- `--config <CONFIG_FILE>`: The path to a configuration file for the simulator.
- `--output <OUTPUT_FILE>`: The path to write the simulation results.
- `--verbose`: Enable verbose logging.
- `--help`: Show help message and exit.
