import pytest
import numpy as np
from src.simulator.main import AdaptiveSimulator
from workloads.cnn_workload import generate_cnn_layer_workload

# Register ABI names for clarity
REG_T0 = 5 # input_addr_reg
REG_T1 = 6 # weight_addr_reg
REG_T0 = 5 # input_addr_reg
REG_T1 = 6 # weight_addr_reg
REG_T2 = 7 # output_addr_reg
REG_A0 = 10
REG_A1 = 11
REG_A2 = 12

@pytest.mark.asyncio
async def test_2_layer_cnn_workload():
    """
    Tests a 2-layer CNN workload.
    """
    # 1. Define network architecture
    layer1_input_shape = (1, 5, 5)
    layer1_kernel_shape = (2, 1, 3, 3) # 2 output channels
    layer2_kernel_shape = (3, 2, 2, 2) # 3 output channels

    # 2. Generate test data
    input_data = np.arange(1, np.prod(layer1_input_shape) + 1, dtype=np.uint32).reshape(layer1_input_shape)
    layer1_weights = np.arange(1, np.prod(layer1_kernel_shape) + 1, dtype=np.uint32).reshape(layer1_kernel_shape)
    layer2_weights = np.arange(1, np.prod(layer2_kernel_shape) + 1, dtype=np.uint32).reshape(layer2_kernel_shape)

    # 3. Generate workload
    layer1_output_height = layer1_input_shape[1] - layer1_kernel_shape[2] + 1
    layer1_output_width = layer1_input_shape[2] - layer1_kernel_shape[3] + 1
    layer1_output_shape = (layer1_kernel_shape[0], layer1_output_height, layer1_output_width)

    reg_config1 = {'input_addr': REG_T0, 'weight_addr': REG_T1, 'output_addr': REG_T2}
    workload1 = generate_cnn_layer_workload(layer1_input_shape, layer1_kernel_shape, reg_config1)

    reg_config2 = {'input_addr': REG_T2, 'weight_addr': REG_A1, 'output_addr': REG_A2}
    workload2 = generate_cnn_layer_workload(layer1_output_shape, layer2_kernel_shape, reg_config2)

    workload = workload1 + workload2
    workload.append(0x0000006F) # halt

    # 4. Initialize simulator and memory
    simulator = AdaptiveSimulator()
    input_addr = 0x1000
    l1_weights_addr = 0x2000
    l1_output_addr = 0x3000
    l2_weights_addr = 0x4000
    final_output_addr = 0x5000

    simulator.risc_v_engine.registers[REG_T0] = input_addr
    simulator.risc_v_engine.registers[REG_T1] = l1_weights_addr
    simulator.risc_v_engine.registers[REG_T2] = l1_output_addr
    simulator.risc_v_engine.registers[REG_A1] = l2_weights_addr
    simulator.risc_v_engine.registers[REG_A2] = final_output_addr

    simulator.bus.write(input_addr, input_data.tobytes())
    simulator.bus.write(l1_weights_addr, layer1_weights.tobytes())
    simulator.bus.write(l2_weights_addr, layer2_weights.tobytes())

    # 5. Run simulation
    simulator.load_program(workload)
    await simulator.run_simulation(max_cycles=len(workload) * 10)

    # 6. Calculate expected output
    # Layer 1
    l1_out = np.zeros(layer1_output_shape, dtype=np.uint32)
    for oc in range(layer1_kernel_shape[0]):
        for i in range(layer1_output_height):
            for j in range(layer1_output_width):
                acc = 0
                for c in range(layer1_input_shape[0]):
                    for ky in range(layer1_kernel_shape[2]):
                        for kx in range(layer1_kernel_shape[3]):
                            acc += input_data[c, i + ky, j + kx] * layer1_weights[oc, c, ky, kx]
                l1_out[oc, i, j] = acc

    # Layer 2
    layer2_output_height = layer1_output_shape[1] - layer2_kernel_shape[2] + 1
    layer2_output_width = layer1_output_shape[2] - layer2_kernel_shape[3] + 1
    expected_output_shape = (layer2_kernel_shape[0], layer2_output_height, layer2_output_width)
    expected_output = np.zeros(expected_output_shape, dtype=np.uint32)
    for oc in range(layer2_kernel_shape[0]):
        for i in range(layer2_output_height):
            for j in range(layer2_output_width):
                acc = 0
                for c in range(layer1_output_shape[0]):
                    for ky in range(layer2_kernel_shape[2]):
                        for kx in range(layer2_kernel_shape[3]):
                            acc += l1_out[c, i + ky, j + kx] * layer2_weights[oc, c, ky, kx]
                expected_output[oc, i, j] = acc

    # 7. Verify final output
    result_bytes = simulator.bus.read(final_output_addr, expected_output.nbytes)
    result = np.frombuffer(result_bytes, dtype=np.uint32).reshape(expected_output_shape)
    np.testing.assert_array_equal(result, expected_output)
