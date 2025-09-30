"""Shared fixtures for integration-level CNN tests."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np
import pytest

try:
    from workloads.cnn_workload import generate_cnn_layer_workload
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip(
        "workloads 패키지가 존재하지 않아 CNN 통합 테스트 픽스처를 건너뜁니다.",
        allow_module_level=True,
    )

try:  # pragma: no cover - Windows/Linux compatibility
    import resource  # type: ignore
except ImportError:  # pragma: no cover - resource 미제공 환경
    resource = None

MemoryKey = pytest.StashKey[Optional[int]]()

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


@dataclass(slots=True)
class MemorySnapshot:
    """Peak RSS measurement captured during CNN 테스트 흐름."""

    label: str
    peak_kib: Optional[int]
    delta_kib: Optional[int]


class MemoryRecorder:
    """Helper to record ru_maxrss deltas during the integration test."""

    def __init__(
        self,
        record_property: Callable[[str, object], None],
        baseline_kib: Optional[int],
    ) -> None:
        self._record_property = record_property
        self._enabled = resource is not None
        self._baseline = baseline_kib if baseline_kib is not None else self._snapshot()
        self._last = self._baseline
        self._snapshots: list[MemorySnapshot] = []

        if not self._enabled:
            self._record_property(
                "cnn_memory_profiler",
                "resource 모듈을 사용할 수 없어 메모리 계측을 건너뜁니다.",
            )
        elif self._baseline is not None:
            self._record_property("cnn_memory_peak_kib_baseline", self._baseline)

    @staticmethod
    def _snapshot() -> Optional[int]:
        if resource is None:  # pragma: no cover - 보호 코드
            return None
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = getattr(usage, "ru_maxrss", None)
        return int(rss) if rss is not None else None

    def capture(self, label: str) -> MemorySnapshot:
        if not self._enabled:
            snapshot = MemorySnapshot(label=label, peak_kib=None, delta_kib=None)
            self._snapshots.append(snapshot)
            return snapshot

        peak = self._snapshot()
        if peak is None:
            snapshot = MemorySnapshot(label=label, peak_kib=None, delta_kib=None)
            self._snapshots.append(snapshot)
            return snapshot

        last = self._last or peak
        delta = max(peak - last, 0)
        self._last = peak
        snapshot = MemorySnapshot(label=label, peak_kib=peak, delta_kib=delta)
        self._snapshots.append(snapshot)

        self._record_property(f"cnn_memory_peak_kib_{label}", peak)
        self._record_property(f"cnn_memory_delta_kib_{label}", delta)
        _logger.info("CNN 메모리 측정 - %s: peak=%sKiB delta=%sKiB", label, peak, delta)
        return snapshot

    def finalize(self) -> None:
        if not self._enabled:
            return
        if not self._snapshots:
            return
        peaks = [snap.peak_kib for snap in self._snapshots if snap.peak_kib is not None]
        if not peaks:
            return
        max_peak = max(peaks)
        self._record_property("cnn_memory_peak_kib_max", max_peak)
        if self._baseline is not None:
            self._record_property("cnn_memory_peak_increase_kib", max_peak - self._baseline)


@pytest.fixture
def cnn_memory_recorder(
    record_property: Callable[[str, object], None],
    pytestconfig: pytest.Config,
) -> MemoryRecorder:
    baseline = pytestconfig.stash.get(MemoryKey, None)
    recorder = MemoryRecorder(record_property, baseline_kib=baseline)
    yield recorder
    recorder.finalize()


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
    if resource is not None:  # pragma: no branch - 단일 경로
        pytestconfig.stash[MemoryKey] = MemoryRecorder._snapshot()
    return _build_two_layer_cnn_scenario(payload_scale)
