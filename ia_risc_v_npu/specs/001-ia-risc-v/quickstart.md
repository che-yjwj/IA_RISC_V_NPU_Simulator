# Quickstart Guide for IA-based RISC-V+NPU Simulator

This guide provides a quick tutorial on how to use the simulator.

## 1. Prerequisites

- Python 3.11 or later
- The simulator installed.

## 2. Running a Simulation

To run a simulation, use the `simulate` command with the path to an ELF file:

```
simulate my_program.elf
```

## 3. Example: Simulating a simple program

1.  **Create a simple C program** (`hello.c`):
    ```c
    #include <stdio.h>

    int main() {
        printf("Hello, world!\n");
        return 0;
    }
    ```

2.  **Compile the program for RISC-V**:
    ```
    riscv64-unknown-elf-gcc -o hello.elf hello.c
    ```

3.  **Run the simulation**:
    ```
    simulate hello.elf
    ```

4.  **Check the output**:
    The simulator should produce output indicating that the program has been executed, and the simulation results will be saved to the specified output file or printed to the console.

