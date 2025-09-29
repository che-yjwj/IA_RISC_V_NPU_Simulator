"""Shared fixtures for integration-level CNN tests."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pytest

try:
    from workloads.cnn_workload import generate_cnn_layer_workload
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip(
        "workloads 패키지가 존재하지 않아 CNN 통합 테스트 픽스처를 건너뜁니다.",
        allow_module_level=True,
    )

HALT_INSTRUCTION = 0x0000006F
MIN_PAYLOAD_SCALE = 0.01

_logger = logging.getLogger(__name__)


@dataclass
class TwoLayerCnnScenario:
    """Container for two-layer CNN integration test data."""

    layer1_input_shape: Tuple[int, int, int]
    layer1_kernel_shape: Tuple[int, int, int, int]
    layer1_output_shape: Tuple[int, int, int]
    layer2_kernel_shape: Tuple[int, int, int, int]
    layer2_output_shape: Tuple[int, int, int]
    input_data: np.ndarray
    layer1_weights: np.ndarray
    layer2_weights: np.ndarray
    workload: List[int]
    payload_scale: float

    @property
    def tensor_bytes(self) -> int:
        """Total bytes consumed by tensors participating in the test."""
        return int(
            self.input_data.nbytes
            + self.layer1_weights.nbytes
            + self.layer2_weights.nbytes
        )

    @property
    def payload_instruction_count(self) -> int:
        """Instruction count excluding the terminating HALT."""
        return max(0, len(self.workload) - 1)

    @property
    def total_instruction_count(self) -> int:
        """Instruction count including HALT."""
        return len(self.workload)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--cnn-payload-scale",
        action="store",
        type=float,
        default=None,
        help=(
            "Scale factor applied to the synthetic NOP payload emitted for the "
            "CNN integration scenario (default: honour CNN_TEST_PAYLOAD_SCALE env "
            "or fall back to 0.05)."
        ),
    )


def _resolve_payload_scale(pytestconfig: pytest.Config) -> float:
    env_value = os.getenv("CNN_TEST_PAYLOAD_SCALE")
    if env_value is not None:
        try:
            payload_scale = float(env_value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise pytest.UsageError(
                "CNN_TEST_PAYLOAD_SCALE 환경 변수는 float 형식이어야 합니다."
            ) from exc
    else:
        cli_value = pytestconfig.getoption("cnn_payload_scale")
        if cli_value is not None:
            payload_scale = float(cli_value)
        else:
            payload_scale = 0.05

    if payload_scale <= 0:
        _logger.warning(
            "음수 또는 0의 payload scale(%s)이 요청되어 %s로 대체합니다.",
            payload_scale,
            MIN_PAYLOAD_SCALE,
        )
        payload_scale = MIN_PAYLOAD_SCALE

    return max(payload_scale, MIN_PAYLOAD_SCALE)


def _build_two_layer_cnn_scenario(payload_scale: float) -> TwoLayerCnnScenario:
    layer1_input_shape = (1, 5, 5)
    layer1_kernel_shape = (2, 1, 3, 3)  # 2 output channels
    layer2_kernel_shape = (3, 2, 2, 2)  # 3 output channels

    input_data = np.arange(
        1, np.prod(layer1_input_shape) + 1, dtype=np.uint32
    ).reshape(layer1_input_shape)
    layer1_weights = np.arange(
        1, np.prod(layer1_kernel_shape) + 1, dtype=np.uint32
    ).reshape(layer1_kernel_shape)
    layer2_weights = np.arange(
        1, np.prod(layer2_kernel_shape) + 1, dtype=np.uint32
    ).reshape(layer2_kernel_shape)

    layer1_output_height = layer1_input_shape[1] - layer1_kernel_shape[2] + 1
    layer1_output_width = layer1_input_shape[2] - layer1_kernel_shape[3] + 1
    layer1_output_shape = (
        layer1_kernel_shape[0], layer1_output_height, layer1_output_width
    )

    layer2_output_height = layer1_output_shape[1] - layer2_kernel_shape[2] + 1
    layer2_output_width = layer1_output_shape[2] - layer2_kernel_shape[3] + 1
    layer2_output_shape = (
        layer2_kernel_shape[0], layer2_output_height, layer2_output_width
    )

    effective_scale = max(payload_scale, MIN_PAYLOAD_SCALE)
    workload1 = generate_cnn_layer_workload(
        layer1_input_shape, layer1_kernel_shape, payload_scale=effective_scale
    )
    workload2 = generate_cnn_layer_workload(
        layer1_output_shape, layer2_kernel_shape, payload_scale=effective_scale
    )

    workload = [*workload1, *workload2, HALT_INSTRUCTION]

    scenario = TwoLayerCnnScenario(
        layer1_input_shape=layer1_input_shape,
        layer1_kernel_shape=layer1_kernel_shape,
        layer1_output_shape=layer1_output_shape,
        layer2_kernel_shape=layer2_kernel_shape,
        layer2_output_shape=layer2_output_shape,
        input_data=input_data,
        layer1_weights=layer1_weights,
        layer2_weights=layer2_weights,
        workload=workload,
        payload_scale=effective_scale,
    )

    _logger.info(
        "준비된 CNN 통합 시나리오: tensor=%.2fKiB, payload_instr=%d, scale=%.2f",
        scenario.tensor_bytes / 1024.0,
        scenario.payload_instruction_count,
        scenario.payload_scale,
    )

    return scenario


@pytest.fixture(scope="module")
def two_layer_cnn_scenario(pytestconfig: pytest.Config) -> TwoLayerCnnScenario:
    payload_scale = _resolve_payload_scale(pytestconfig)
    return _build_two_layer_cnn_scenario(payload_scale)
