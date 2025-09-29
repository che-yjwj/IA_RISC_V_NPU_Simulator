import asyncio

import numpy as np

from src.simulator.cnn_runtime import run_cnn_layer
from src.simulator.main import AdaptiveSimulator

# Register ABI names for clarity
REG_T0 = 5  # input_addr_reg
REG_T1 = 6  # weight_addr_reg
REG_T2 = 7  # output_addr_reg
REG_A0 = 10
REG_A1 = 11
REG_A2 = 12

# Memory Addresses
INPUT_ADDR = 0x1000
L1_WEIGHTS_ADDR = 0x2000
L1_OUTPUT_ADDR = 0x3000
L2_WEIGHTS_ADDR = 0x4000
FINAL_OUTPUT_ADDR = 0x5000


def test_2_layer_cnn_workload(two_layer_cnn_scenario, record_property):
    """
    Tests a 2-layer CNN workload.
    """
    scenario = two_layer_cnn_scenario

    record_property("cnn_tensor_bytes", scenario.tensor_bytes)
    record_property("cnn_payload_scale", scenario.payload_scale)
    record_property(
        "cnn_payload_instructions", scenario.payload_instruction_count
    )

    # 4. Initialize simulator and memory
    simulator = AdaptiveSimulator()
    simulator.risc_v_engine.registers[REG_T0] = INPUT_ADDR
    simulator.risc_v_engine.registers[REG_T1] = L1_WEIGHTS_ADDR
    simulator.risc_v_engine.registers[REG_T2] = L1_OUTPUT_ADDR
    simulator.risc_v_engine.registers[REG_A1] = L2_WEIGHTS_ADDR
    simulator.risc_v_engine.registers[REG_A2] = FINAL_OUTPUT_ADDR

    simulator.bus.write(INPUT_ADDR, scenario.input_data.tobytes())
    simulator.bus.write(L1_WEIGHTS_ADDR, scenario.layer1_weights.tobytes())
    simulator.bus.write(L2_WEIGHTS_ADDR, scenario.layer2_weights.tobytes())

    workload = scenario.workload
    simulator.load_program(workload)

    # 6. Calculate expected output (시뮬레이션 전 계산)
    # Layer 1
    l1_out = np.zeros(scenario.layer1_output_shape, dtype=np.uint32)
    for oc in range(scenario.layer1_kernel_shape[0]):
        for i in range(scenario.layer1_output_shape[1]):
            for j in range(scenario.layer1_output_shape[2]):
                receptive_field = scenario.input_data[
                    :,
                    i : i + scenario.layer1_kernel_shape[2],
                    j : j + scenario.layer1_kernel_shape[3],
                ]
                l1_out[oc, i, j] = np.sum(
                    receptive_field * scenario.layer1_weights[oc]
                )

    # Layer 2
    expected_output = np.zeros(scenario.layer2_output_shape, dtype=np.uint32)
    for oc in range(scenario.layer2_kernel_shape[0]):
        for i in range(scenario.layer2_output_shape[1]):
            for j in range(scenario.layer2_output_shape[2]):
                receptive_field = l1_out[
                    :,
                    i : i + scenario.layer2_kernel_shape[2],
                    j : j + scenario.layer2_kernel_shape[3],
                ]
                expected_output[oc, i, j] = np.sum(
                    receptive_field * scenario.layer2_weights[oc]
                )

    report = asyncio.run(
        simulator.run_simulation(max_cycles=len(workload) * 10)
    )

    run_cnn_layer(
        simulator.bus,
        INPUT_ADDR,
        L1_WEIGHTS_ADDR,
        L1_OUTPUT_ADDR,
        scenario.layer1_input_shape,
        scenario.layer1_kernel_shape,
    )

    run_cnn_layer(
        simulator.bus,
        L1_OUTPUT_ADDR,
        L2_WEIGHTS_ADDR,
        FINAL_OUTPUT_ADDR,
        scenario.layer1_output_shape,
        scenario.layer2_kernel_shape,
    )

    # 7. Verify final output
    result_bytes = simulator.bus.read(
        FINAL_OUTPUT_ADDR, expected_output.nbytes
    )
    result = np.frombuffer(result_bytes, dtype=np.uint32).reshape(
        scenario.layer2_output_shape
    )
    np.testing.assert_array_equal(result, expected_output)
    assert report.instructions == len(workload)
    expected_pc = len(workload) * 4 - 4
    assert simulator.risc_v_engine.pc == expected_pc
    assert report.halted
