"""CNN workload generators used by integration tests and tooling."""

from __future__ import annotations

from typing import List, Sequence

from src.simulator.cnn_utils import estimate_mac_count

ADD_NOP_INSTRUCTION = 0x00000033  # add x0, x0, x0 -> no-op


def _build_instruction_stream(payload_length: int) -> List[int]:
    payload_length = max(1, payload_length)
    return [ADD_NOP_INSTRUCTION] * payload_length


def generate_cnn_workload(
    input_shape: Sequence[int],
    kernel_shape: Sequence[int],
    *,
    payload_scale: float = 1.0,
) -> List[int]:
    """Return a simple NOP-based program sized to the convolution workload.

    Args:
        input_shape: (in_channels, height, width)
        kernel_shape: (out_channels, in_channels, kernel_h, kernel_w) 또는 (in_channels, kernel_h, kernel_w)
        payload_scale: 필요 시 명령 수를 확대하기 위한 배율
    """
    macs = estimate_mac_count(input_shape, kernel_shape)
    payload = int(max(1, round(macs * max(payload_scale, 0.0))))
    return _build_instruction_stream(payload)


def generate_cnn_layer_workload(
    input_shape: Sequence[int],
    kernel_shape: Sequence[int],
    *,
    payload_scale: float = 1.0,
) -> List[int]:
    """Alias maintained for backwards compatibility."""
    return generate_cnn_workload(
        input_shape, kernel_shape, payload_scale=payload_scale
    )


__all__ = ["generate_cnn_workload", "generate_cnn_layer_workload"]
