import pytest
import numpy as np
from src.simulator.main import AdaptiveSimulator
from workloads.cnn_workload import generate_cnn_workload

# Register ABI names for clarity
REG_T0 = 5 # input_addr_reg
REG_T1 = 6 # weight_addr_reg
REG_T2 = 7 # output_addr_reg

@pytest.mark.parametrize("input_shape, kernel_shape", [
    ((1, 3, 3), (1, 2, 2)),
    ((2, 4, 4), (2, 2, 2)),
    ((1, 5, 5), (1, 3, 3)),
])
@pytest.mark.asyncio
async def test_run_cnn_workload_with_verification(input_shape, kernel_shape):
    """
    Tests running a generated 2D CNN workload on the simulator and verifies the results.
    """
    # 1. Generate test data
    channels, height, width = input_shape
    _, kernel_height, kernel_width = kernel_shape
    input_data = np.arange(1, channels * height * width + 1, dtype=np.uint32).reshape(input_shape)
    weights = np.arange(1, channels * kernel_height * kernel_width + 1, dtype=np.uint32).reshape(kernel_shape)

    # 2. Generate the CNN workload
    reg_config = {
        'input_addr': REG_T0,
        'weight_addr': REG_T1,
        'output_addr': REG_T2,
    }
    workload = generate_cnn_workload(input_shape, kernel_shape, reg_config)
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
    # Run with a generous cycle limit, relying on the halt instruction
    await simulator.run_simulation(max_cycles=len(workload) * 10)

    # 5. Calculate expected output
    output_height = height - kernel_height + 1
    output_width = width - kernel_width + 1
    expected_output = np.zeros((output_height, output_width), dtype=np.uint32)
    for i in range(output_height):
        for j in range(output_width):
            acc = 0
            for c in range(channels):
                for ky in range(kernel_height):
                    for kx in range(kernel_width):
                        input_val = input_data[c, i + ky, j + kx]
                        weight_val = weights[c, ky, kx]
                        acc += input_val * weight_val
            expected_output[i, j] = acc

    # 6. Read output from memory and verify
    output_size_bytes = expected_output.nbytes
    result_bytes = simulator.bus.read(output_addr, output_size_bytes)
    result = np.frombuffer(result_bytes, dtype=np.uint32).reshape(expected_output.shape)
    np.testing.assert_array_equal(result, expected_output)

    # Also check the PC to ensure it halted at the last instruction
    expected_pc = len(workload) * 4 - 4
    assert simulator.risc_v_engine.pc == expected_pc
