"""Shared fixtures for integration-level CNN tests."""

from __future__ import annotations

import logging
import os
import tracemalloc
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


@dataclass(slots=True)
class TraceSnapshot:
    """tracemalloc 측정 결과."""

    label: str
    current_kib: float
    peak_kib: float
    top_stats: List[str]


class MemoryRecorder:
    """Helper to record ru_maxrss deltas during the integration test."""

    def __init__(
        self,
        record_property: Callable[[str, object], None],
        baseline_kib: Optional[int],
        *,
        enable_tracemalloc: bool = False,
        tracemalloc_frames: int = 25,
        tracemalloc_top_stats: int = 5,
    ) -> None:
        self._record_property = record_property
        self._enabled = resource is not None
        self._baseline = baseline_kib if baseline_kib is not None else self._snapshot()
        self._last = self._baseline
        self._snapshots: list[MemorySnapshot] = []
        self._trace_enabled = enable_tracemalloc
        self._trace_top_stats = max(0, tracemalloc_top_stats)
        self._trace_snapshots: list[TraceSnapshot] = []
        self._trace_started_by_recorder = False
        self._trace_baseline_snapshot: Optional["tracemalloc.Snapshot"] = None

        if self._trace_enabled:
            if not tracemalloc.is_tracing():  # pragma: no branch - 단일 경로
                tracemalloc.start(tracemalloc_frames)
                self._trace_started_by_recorder = True
                tracemalloc.clear_traces()
            try:
                self._trace_baseline_snapshot = tracemalloc.take_snapshot()
            except RuntimeError:  # pragma: no cover - 추적 종료 경합 보호
                self._trace_baseline_snapshot = None
            self._record_property("cnn_tracemalloc_frames", tracemalloc_frames)
            self._record_property("cnn_tracemalloc_top", self._trace_top_stats)

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
        else:
            peak = self._snapshot()
            if peak is None:
                snapshot = MemorySnapshot(label=label, peak_kib=None, delta_kib=None)
                self._snapshots.append(snapshot)
            else:
                last = self._last or peak
                delta = max(peak - last, 0)
                self._last = peak
                snapshot = MemorySnapshot(label=label, peak_kib=peak, delta_kib=delta)
                self._snapshots.append(snapshot)

                self._record_property(f"cnn_memory_peak_kib_{label}", peak)
                self._record_property(f"cnn_memory_delta_kib_{label}", delta)
                _logger.info(
                    "CNN 메모리 측정 - %s: peak=%sKiB delta=%sKiB",
                    label,
                    peak,
                    delta,
                )

        if self._trace_enabled and tracemalloc.is_tracing():
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            current_kib = current_bytes / 1024.0
            peak_kib = peak_bytes / 1024.0
            top_entries: List[str] = []
            if self._trace_top_stats > 0:
                try:
                    snapshot = tracemalloc.take_snapshot()
                except RuntimeError:  # pragma: no cover - 추적 종료 경합 보호
                    snapshot = None
                if snapshot is not None:
                    stats_entries: List[tuple[str, float]] = []
                    if self._trace_baseline_snapshot is not None:
                        diffs = snapshot.compare_to(
                            self._trace_baseline_snapshot, "lineno"
                        )
                        diffs = [
                            stat
                            for stat in diffs
                            if getattr(stat, "size_diff", 0) > 0
                        ][: self._trace_top_stats]
                        stats_entries = [
                            (
                                stat.traceback[0],
                                getattr(stat, "size_diff", 0) / 1024.0,
                            )
                            for stat in diffs
                        ]
                    else:
                        stats = snapshot.statistics("lineno")[: self._trace_top_stats]
                        stats_entries = [
                            (stat.traceback[0], stat.size / 1024.0)
                            for stat in stats
                        ]
                    top_entries = [
                        f"{trace}: {size_kib:.1f}KiB"
                        for trace, size_kib in stats_entries
                    ]
                    self._trace_baseline_snapshot = snapshot
            trace_snapshot = TraceSnapshot(
                label=label,
                current_kib=current_kib,
                peak_kib=peak_kib,
                top_stats=top_entries,
            )
            self._trace_snapshots.append(trace_snapshot)
            self._record_property(
                f"cnn_tracemalloc_current_kib_{label}", round(current_kib, 3)
            )
            self._record_property(
                f"cnn_tracemalloc_peak_kib_{label}", round(peak_kib, 3)
            )
            if top_entries:
                self._record_property(
                    f"cnn_tracemalloc_top_{label}",
                    top_entries,
                )
            _logger.debug(  # pragma: no cover - 디버그 로깅
                "CNN tracemalloc - %s: current=%.1fKiB peak=%.1fKiB",
                label,
                current_kib,
                peak_kib,
            )

        return snapshot

    def finalize(self) -> None:
        if self._enabled and self._snapshots:
            peaks = [
                snap.peak_kib for snap in self._snapshots if snap.peak_kib is not None
            ]
            if peaks:
                max_peak = max(peaks)
                self._record_property("cnn_memory_peak_kib_max", max_peak)
                if self._baseline is not None:
                    self._record_property(
                        "cnn_memory_peak_increase_kib", max_peak - self._baseline
                    )

        if self._trace_enabled:
            if self._trace_snapshots:
                peak_values = [snap.peak_kib for snap in self._trace_snapshots]
                overall_peak = max(peak_values)
                self._record_property(
                    "cnn_tracemalloc_peak_kib_max", round(overall_peak, 3)
                )
                label, peak_value = max(
                    ((snap.label, snap.peak_kib) for snap in self._trace_snapshots),
                    key=lambda item: item[1],
                )
                self._record_property(
                    "cnn_tracemalloc_peak_label",
                    {"label": label, "peak_kib": round(peak_value, 3)},
                )
                if self._trace_top_stats > 0:
                    self._record_property(
                        "cnn_tracemalloc_top_events",
                        {
                            snap.label: snap.top_stats
                            for snap in self._trace_snapshots
                            if snap.top_stats
                        },
                    )
            if self._trace_started_by_recorder and tracemalloc.is_tracing():
                tracemalloc.stop()


@pytest.fixture
def cnn_memory_recorder(
    record_property: Callable[[str, object], None],
    pytestconfig: pytest.Config,
) -> MemoryRecorder:
    baseline = pytestconfig.stash.get(MemoryKey, None)
    trace_enabled = _resolve_trace_enabled(pytestconfig)
    trace_frames, trace_top = _resolve_trace_params()
    recorder = MemoryRecorder(
        record_property,
        baseline_kib=baseline,
        enable_tracemalloc=trace_enabled,
        tracemalloc_frames=trace_frames,
        tracemalloc_top_stats=trace_top,
    )
    yield recorder
    recorder.finalize()


def _resolve_trace_enabled(pytestconfig: pytest.Config) -> bool:
    cli_flag = pytestconfig.getoption("cnn_memory_trace")
    env_flag = os.getenv("CNN_MEMORY_TRACE")
    if env_flag is not None:
        normalized = env_flag.strip().lower()
        if normalized in {"", "0", "false", "no", "off"}:
            return False
        return True
    return bool(cli_flag)


def _resolve_trace_params() -> Tuple[int, int]:
    frames_env = os.getenv("CNN_MEMORY_TRACE_FRAMES")
    top_env = os.getenv("CNN_MEMORY_TRACE_TOP")
    frames = 25
    top = 5
    if frames_env:
        try:
            frames = max(1, int(frames_env))
        except ValueError:  # pragma: no cover - 방어 코드
            _logger.warning(
                "CNN_MEMORY_TRACE_FRAMES=%s 값을 int 로 변환하지 못해 기본값 %d을 사용합니다.",
                frames_env,
                frames,
            )
    if top_env:
        try:
            top = max(0, int(top_env))
        except ValueError:  # pragma: no cover - 방어 코드
            _logger.warning(
                "CNN_MEMORY_TRACE_TOP=%s 값을 int 로 변환하지 못해 기본값 %d을 사용합니다.",
                top_env,
                top,
            )
    return frames, top


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
    parser.addoption(
        "--cnn-memory-trace",
        action="store_true",
        default=False,
        help=(
            "tracemalloc 기반 CNN 통합 테스트 메모리 추적을 활성화합니다. "
            "환경 변수 CNN_MEMORY_TRACE=1 로도 제어할 수 있습니다."
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
