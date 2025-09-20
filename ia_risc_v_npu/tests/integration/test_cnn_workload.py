import pytest
import numpy as np
import time
from src.simulator.main import AdaptiveSimulator
from workloads.cnn_workload import generate_cnn_layer_workload

# Register ABI names for clarity
REG_T0 = 5  # input_addr_reg
REG_T1 = 6  # weight_addr_reg
REG_T2 = 7  # output_addr_reg

# Parametrize with (input_shape, (out_channels, kernel_height, kernel_width))
@pytest.mark.parametrize("input_shape, kernel_config", [
    ((1, 3, 3), (1, 2, 2)),  # in_channels=1, out_channels=1
    ((2, 4, 4), (3, 2, 2)),  # in_channels=2, out_channels=3
    ((1, 5, 5), (2, 3, 3)),  # in_channels=1, out_channels=2
    ((1, 16, 16), (1, 4, 4)), # Larger test case
])
@pytest.mark.asyncio
async def test_run_cnn_workload_with_verification(input_shape, kernel_config):
    """
    Tests running a generated 2D CNN workload on the simulator, verifies the results, and measures performance.
    """
    # 1. Generate test data
    in_channels, height, width = input_shape
    out_channels, kernel_height, kernel_width = kernel_config

    # Define full shapes
    full_input_shape = (in_channels, height, width)
    full_kernel_shape = (out_channels, in_channels, kernel_height, kernel_width)

    input_data = np.arange(1, full_input_shape[0] * full_input_shape[1] * full_input_shape[2] + 1, dtype=np.uint32).reshape(full_input_shape)
    weights = np.arange(1, full_kernel_shape[0] * full_kernel_shape[1] * full_kernel_shape[2] * full_kernel_shape[3] + 1, dtype=np.uint32).reshape(full_kernel_shape)

    # 2. Generate the CNN workload
    reg_config = {
        'input_addr': REG_T0,
        'weight_addr': REG_T1,
        'output_addr': REG_T2,
    }
    workload = generate_cnn_layer_workload(full_input_shape, full_kernel_shape, reg_config)
    print(f"Workload length: {len(workload)}")
    # Add a halt instruction (JAL x0, 0) to the end
    workload.append(0x0000006F)
    # 3. Initialize the simulator and memory
    simulator = AdaptiveSimulator()
    input_addr = 0x1000
    weights_addr = 0x2000
    output_addr = 0x3000

    simulator.risc_v_engine.registers[REG_T0] = input_addr
    simulator.risc_v_engine.registers[REG_T1] = weights_addr
    simulator.risc_v_engine.registers[REG_T2] = output_addr

    # Write input and weights to memory
    simulator.bus.write(input_addr, input_data.tobytes())
    simulator.bus.write(weights_addr, weights.tobytes())

    # 4. Load and run the program
    simulator.load_program(workload)

    # Reset instruction counter and start timer
    simulator.risc_v_engine.instruction_count = 0
    start_time = time.perf_counter()

    # Run with a generous cycle limit, relying on the halt instruction
    await simulator.run_simulation(max_cycles=len(workload) * 20) # Increased max_cycles just in case

    end_time = time.perf_counter()

    # 5. Calculate and report MIPS
    execution_time = end_time - start_time
    instructions_executed = simulator.risc_v_engine.instruction_count
    if execution_time > 0:
        mips = (instructions_executed / execution_time) / 1_000_000
    else:
        mips = float('inf')

    print(f"\n--- CNN Workload Performance ---")
    print(f"Parameters: input={full_input_shape}, kernel={full_kernel_shape}")
    print(f"Instructions: {instructions_executed}")
    print(f"Execution Time: {execution_time:.6f}s")
    print(f"Performance: {mips:.2f} MIPS")
    print(f"------------------------------------")

    # 6. Calculate expected output
    output_height = height - kernel_height + 1
    output_width = width - kernel_width + 1
    expected_output = np.zeros((out_channels, output_height, output_width), dtype=np.uint32)
    for oc in range(out_channels):
        for i in range(output_height):
            for j in range(output_width):
                acc = 0
                for c in range(in_channels):
                    for ky in range(kernel_height):
                        for kx in range(kernel_width):
                            input_val = input_data[c, i + ky, j + kx]
                            weight_val = weights[oc, c, ky, kx]
                            acc += input_val * weight_val
                expected_output[oc, i, j] = acc

    # 7. Read output from memory and verify
    output_size_bytes = expected_output.nbytes
    result_bytes = simulator.bus.read(output_addr, output_size_bytes)
    result = np.frombuffer(result_bytes, dtype=np.uint32).reshape(expected_output.shape)
    np.testing.assert_array_equal(result, expected_output)

    # Also check the PC to ensure it halted at the last instruction
    # The workload generator produces a list of instructions, so the address of the last instruction is (len(workload) - 1) * 4
    expected_pc = (len(workload) - 1) * 4
    assert simulator.risc_v_engine.pc == expected_pc