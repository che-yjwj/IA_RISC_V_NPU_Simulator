import asyncio
import numpy as np
import pytest

from src.simulator.main import AdaptiveSimulator
from src.simulator.cnn_runtime import run_cnn_layer

try:
    from workloads.cnn_workload import generate_cnn_workload
except ModuleNotFoundError:  # pragma: no cover - optional workload package
    pytestmark = pytest.mark.skip(reason="workloads 패키지가 존재하지 않아 CNN 워크로드 테스트를 건너뜁니다.")

# Register ABI names for clarity
REG_T0 = 5  # input_addr_reg
REG_T1 = 6  # weight_addr_reg
REG_T2 = 7  # output_addr_reg


@pytest.mark.parametrize(
    "input_shape, kernel_shape",
    [
        ((1, 3, 3), (1, 1, 2, 2)),
        ((2, 4, 4), (3, 2, 2, 2)),
        ((1, 5, 5), (2, 1, 3, 3)),
    ],
)
def test_run_cnn_workload_with_verification(input_shape, kernel_shape):
    """Run a generated CNN workload, execute the math model, and verify output."""

    # 1. Generate test data
    in_channels, height, width = input_shape
    out_channels, _, kernel_height, kernel_width = kernel_shape
    input_data = np.arange(1, np.prod(input_shape) + 1, dtype=np.uint32).reshape(input_shape)
    weights = np.arange(1, np.prod(kernel_shape) + 1, dtype=np.uint32).reshape(kernel_shape)

    # 2. Generate workload
    workload = generate_cnn_workload(input_shape, kernel_shape)
    workload.append(0x0000006F)  # halt instruction

    # 3. Initialize simulator
    simulator = AdaptiveSimulator()
    input_addr = 0x20000
    weights_addr = 0x30000
    output_addr = 0x40000

    simulator.risc_v_engine.registers[REG_T0] = input_addr
    simulator.risc_v_engine.registers[REG_T1] = weights_addr
    simulator.risc_v_engine.registers[REG_T2] = output_addr

    simulator.bus.write(input_addr, input_data.tobytes())
    simulator.bus.write(weights_addr, weights.tobytes())
    simulator.load_program(workload)

    report = asyncio.run(simulator.run_simulation(max_cycles=len(workload) * 10))

    # 4. Execute the reference CNN layer and write results back
    run_cnn_layer(
        simulator.bus,
        input_addr,
        weights_addr,
        output_addr,
        input_shape,
        kernel_shape,
    )

    # 5. Verify output against NumPy reference
    output_height = height - kernel_height + 1
    output_width = width - kernel_width + 1
    expected_output = np.zeros((out_channels, output_height, output_width), dtype=np.uint32)
    for oc in range(out_channels):
        for oy in range(output_height):
            for ox in range(output_width):
                region = input_data[:, oy : oy + kernel_height, ox : ox + kernel_width]
                expected_output[oc, oy, ox] = np.sum(region * weights[oc])

    output_size_bytes = expected_output.nbytes
    result_bytes = simulator.bus.read(output_addr, output_size_bytes)
    result = np.frombuffer(result_bytes, dtype=np.uint32).reshape(expected_output.shape)
    np.testing.assert_array_equal(result, expected_output)

    # 6. Ensure simulator halted at expected PC and collected stats
    expected_pc = len(workload) * 4 - 4
    assert simulator.risc_v_engine.pc == expected_pc
    assert report.instructions == len(workload)
    assert report.halted
