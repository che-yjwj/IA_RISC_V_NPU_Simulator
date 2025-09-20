"""단순 CNN 계층 실행 헬퍼.

이 모듈은 시뮬레이터 메모리 버스에서 입력/가중치를 읽어
컨볼루션 결과를 계산한 뒤 다시 버스에 기록한다.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from src.simulator.memory import Bus
from src.simulator.cnn_utils import compute_output_dims, normalize_kernel_shape


def _reshape_input(bus: Bus, addr: int, shape: Sequence[int]) -> np.ndarray:
    byte_len = np.prod(shape, dtype=np.int64) * 4
    data = bus.read(addr, int(byte_len))
    return np.frombuffer(memoryview(data), dtype=np.uint32).reshape(shape)


def _reshape_weights(bus: Bus, addr: int, shape: Sequence[int]) -> np.ndarray:
    byte_len = np.prod(shape, dtype=np.int64) * 4
    data = bus.read(addr, int(byte_len))
    return np.frombuffer(memoryview(data), dtype=np.uint32).reshape(shape)


def run_cnn_layer(
    bus: Bus,
    input_addr: int,
    weight_addr: int,
    output_addr: int,
    input_shape: Sequence[int],
    kernel_shape: Sequence[int],
) -> np.ndarray:
    """단일 CNN 레이어를 실행하고 결과를 버스에 기록한다.

    Args:
        bus: 시뮬레이터 메모리 버스
        input_addr: 입력 텐서 시작 주소
        weight_addr: 커널 텐서 시작 주소
        output_addr: 출력 텐서 기록 주소
        input_shape: (채널, 높이, 너비)
        kernel_shape: (채널, kH, kW) 또는 (out, in, kH, kW)

    Returns:
        계산된 출력 텐서를 `np.uint32` 배열로 반환한다.
    """
    input_tensor = _reshape_input(bus, input_addr, input_shape).astype(np.uint64)
    weights = _reshape_weights(bus, weight_addr, kernel_shape).astype(np.uint64)

    out_channels, channels, kernel_h, kernel_w = normalize_kernel_shape(
        input_shape, kernel_shape
    )
    if len(kernel_shape) == 3:
        weights = weights.reshape(1, *weights.shape)

    out_h, out_w = compute_output_dims(input_shape, kernel_shape)
    output = np.zeros((out_channels, out_h, out_w), dtype=np.uint64)

    for oc in range(out_channels):
        weight_slice = weights[oc]
        for oy in range(out_h):
            for ox in range(out_w):
                region = input_tensor[:, oy : oy + kernel_h, ox : ox + kernel_w]
                acc = 0
                for c in range(channels):
                    acc += np.sum(region[c] * weight_slice[c])
                output[oc, oy, ox] = acc

    out_bytes = output.astype(np.uint32).tobytes()
    bus.write(output_addr, out_bytes)
    return output.astype(np.uint32)


__all__ = ["run_cnn_layer"]
