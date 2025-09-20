import pytest
import numpy as np
from src.simulator.main import AdaptiveSimulator
from workloads.cnn_workload import generate_cnn_workload

@pytest.mark.parametrize("channels, height, width, kernel_size", [
    (1, 3, 3, 2),
    (2, 4, 4, 2),
    (1, 5, 5, 3),
])
@pytest.mark.asyncio
async def test_run_cnn_workload_with_verification(channels, height, width, kernel_size):
    """
    Tests running a generated CNN workload on the simulator and verifies the results.
    """
    # 1. Generate test data
    input_data = np.arange(1, channels * height * width + 1, dtype=np.uint32)
    weights = np.arange(1, channels + 1, dtype=np.uint32)

    # 2. Generate the CNN workload
    workload = generate_cnn_workload(channels, height, width, kernel_size)

    # 3. Initialize the simulator and memory
    simulator = AdaptiveSimulator()
    input_addr = 0x1000
    weights_addr = 0x2000
    output_addr = 0x3000

    simulator.risc_v_engine.registers[5] = input_addr
    simulator.risc_v_engine.registers[6] = weights_addr
    simulator.risc_v_engine.registers[4] = output_addr

    # Write input and weights to memory
    for i, val in enumerate(input_data):
        simulator.bus.write(input_addr + i * 4, val.tobytes())
    for i, val in enumerate(weights):
        simulator.bus.write(weights_addr + i * 4, val.tobytes())

    # 4. Load and run the program
    simulator.load_program(workload)
    await simulator.run_simulation(max_cycles=len(workload))

    # 5. Calculate expected output
    output_height = height - kernel_size + 1
    output_width = width - kernel_size + 1
    expected_output = np.zeros((output_height, output_width), dtype=np.uint32)
    for i in range(output_height):
        for j in range(output_width):
            acc = 0
            for k in range(channels):
                input_val = input_data[i * width + j + k]
                weight_val = weights[k]
                acc += input_val * weight_val
            expected_output[i, j] = acc

    # 6. Read output from memory and verify
    for i in range(output_height):
        for j in range(output_width):
            offset = (i * output_width + j) * 4
            result_bytes = simulator.bus.read(output_addr + offset, 4)
            result = np.frombuffer(result_bytes, dtype=np.uint32)[0]
            assert result == expected_output[i, j]

    # Also check the PC
    expected_pc = len(workload) * 4
    assert simulator.risc_v_engine.pc == expected_pc