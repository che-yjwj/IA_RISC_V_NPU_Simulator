"""CNN shape utility helpers shared across simulator and workload generators."""

from __future__ import annotations

from typing import Sequence, Tuple


def normalize_kernel_shape(
    input_shape: Sequence[int], kernel_shape: Sequence[int]
) -> Tuple[int, int, int, int]:
    """Return (out_channels, in_channels, kernel_h, kernel_w)."""
    in_channels = int(input_shape[0])
    if len(kernel_shape) == 3:
        channels, kernel_h, kernel_w = map(int, kernel_shape)
        if channels != in_channels:
            raise ValueError(
                f"입력 채널 수({in_channels})와 커널 채널 수({channels})가 다릅니다."
            )
        return 1, channels, kernel_h, kernel_w
    if len(kernel_shape) == 4:
        out_channels, channels, kernel_h, kernel_w = map(int, kernel_shape)
        if channels != in_channels:
            raise ValueError(
                f"입력 채널 수({in_channels})와 커널 채널 수({channels})가 다릅니다."
            )
        return out_channels, channels, kernel_h, kernel_w
    raise ValueError("지원하지 않는 커널 차원입니다.")


def compute_output_dims(
    input_shape: Sequence[int], kernel_shape: Sequence[int]
) -> Tuple[int, int]:
    """Compute convolution output height/width."""
    _, input_h, input_w = input_shape
    kernel_h, kernel_w = normalize_kernel_shape(input_shape, kernel_shape)[2:]
    out_h = input_h - kernel_h + 1
    out_w = input_w - kernel_w + 1
    if out_h <= 0 or out_w <= 0:
        raise ValueError("커널이 입력보다 커서 출력 크기가 유효하지 않습니다.")
    return out_h, out_w


def estimate_mac_count(
    input_shape: Sequence[int], kernel_shape: Sequence[int]
) -> int:
    """Roughly estimate MAC operations for a convolution layer."""
    out_channels, in_channels, kernel_h, kernel_w = normalize_kernel_shape(
        input_shape, kernel_shape
    )
    out_h, out_w = compute_output_dims(input_shape, kernel_shape)
    macs = out_channels * in_channels * out_h * out_w * kernel_h * kernel_w
    return max(1, int(macs))


__all__ = ["normalize_kernel_shape", "compute_output_dims", "estimate_mac_count"]
