"""Generate deterministic assets for the two-layer CNN integration workload."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

try:
    from workloads.cnn_workload import generate_cnn_workload
except ModuleNotFoundError:  # pragma: no cover - best effort direct execution guard
    import sys

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    src_root = package_root / "src"
    if src_root.exists() and str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from workloads.cnn_workload import generate_cnn_workload

HALT_INSTRUCTION = 0x0000006F
DEFAULT_OUTPUT_DIR = Path("workloads/generated/two_layer_cnn")
LAYER1_INPUT_SHAPE = (1, 5, 5)
LAYER1_KERNEL_SHAPE = (2, 1, 3, 3)
LAYER2_KERNEL_SHAPE = (3, 2, 2, 2)


@dataclass(frozen=True)
class CnnAssetMetadata:
    layer1_input_shape: Tuple[int, int, int]
    layer1_kernel_shape: Tuple[int, int, int, int]
    layer2_kernel_shape: Tuple[int, int, int, int]
    layer1_output_shape: Tuple[int, int, int]
    layer2_output_shape: Tuple[int, int, int]
    payload_scale: float
    halt_instruction: int
    dtype: str
    program_length: int


def _derive_output_shape(
    input_shape: Tuple[int, int, int], kernel_shape: Tuple[int, int, int, int]
) -> Tuple[int, int, int]:
    channels, height, width = input_shape
    _, _, kernel_h, kernel_w = kernel_shape
    output_h = height - kernel_h + 1
    output_w = width - kernel_w + 1
    return kernel_shape[0], output_h, output_w


def _ensure_output_dir(path: Path, *, force: bool) -> None:
    if path.exists():
        if not path.is_dir():
            raise SystemExit(f"{path} is not a directory")
        if any(path.iterdir()) and not force:
            raise SystemExit(
                f"{path} already contains files. Re-run with --force to overwrite."
            )
    path.mkdir(parents=True, exist_ok=True)


def _build_tensors(dtype: np.dtype) -> Dict[str, np.ndarray]:
    input_data = np.arange(1, np.prod(LAYER1_INPUT_SHAPE) + 1, dtype=dtype).reshape(
        LAYER1_INPUT_SHAPE
    )
    layer1_weights = np.arange(
        1, np.prod(LAYER1_KERNEL_SHAPE) + 1, dtype=dtype
    ).reshape(LAYER1_KERNEL_SHAPE)
    layer2_weights = np.arange(
        1, np.prod(LAYER2_KERNEL_SHAPE) + 1, dtype=dtype
    ).reshape(LAYER2_KERNEL_SHAPE)
    return {
        "input": input_data,
        "layer1_weights": layer1_weights,
        "layer2_weights": layer2_weights,
    }


def _build_program(
    payload_scale: float,
) -> Tuple[np.ndarray, Tuple[int, int, int], Tuple[int, int, int]]:
    layer1_output_shape = _derive_output_shape(LAYER1_INPUT_SHAPE, LAYER1_KERNEL_SHAPE)
    layer2_output_shape = _derive_output_shape(layer1_output_shape, LAYER2_KERNEL_SHAPE)

    layer1_program = generate_cnn_workload(
        LAYER1_INPUT_SHAPE, LAYER1_KERNEL_SHAPE, payload_scale=payload_scale
    )
    layer2_program = generate_cnn_workload(
        layer1_output_shape, LAYER2_KERNEL_SHAPE, payload_scale=payload_scale
    )
    program = np.array(
        [*layer1_program, *layer2_program, HALT_INSTRUCTION], dtype=np.uint32
    )
    return program, layer1_output_shape, layer2_output_shape


def _write_arrays(output_dir: Path, tensors: Dict[str, np.ndarray]) -> None:
    for name, array in tensors.items():
        target = output_dir / f"{name}.npy"
        np.save(target, array)


def _write_program(output_dir: Path, program: np.ndarray) -> None:
    np.save(output_dir / "program.npy", program)


def _write_metadata(output_dir: Path, metadata: CnnAssetMetadata) -> None:
    target = output_dir / "metadata.json"
    target.write_text(
        json.dumps(asdict(metadata), indent=2, sort_keys=True), encoding="utf-8"
    )


def generate_assets(
    output_dir: Path, *, payload_scale: float, dtype_name: str, force: bool
) -> Path:
    dtype = np.dtype(dtype_name)
    _ensure_output_dir(output_dir, force=force)

    tensors = _build_tensors(dtype)
    program, layer1_output_shape, layer2_output_shape = _build_program(payload_scale)

    _write_arrays(output_dir, tensors)
    _write_program(output_dir, program)

    metadata = CnnAssetMetadata(
        layer1_input_shape=LAYER1_INPUT_SHAPE,
        layer1_kernel_shape=LAYER1_KERNEL_SHAPE,
        layer2_kernel_shape=LAYER2_KERNEL_SHAPE,
        layer1_output_shape=layer1_output_shape,
        layer2_output_shape=layer2_output_shape,
        payload_scale=payload_scale,
        halt_instruction=HALT_INSTRUCTION,
        dtype=dtype.str,
        program_length=int(program.size),
    )
    _write_metadata(output_dir, metadata)
    return output_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic tensor and program assets for the two-layer CNN "
            "scenario."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory where artifacts are written (default: "
            "workloads/generated/two_layer_cnn)"
        ),
    )
    parser.add_argument(
        "--payload-scale",
        type=float,
        default=0.05,
        help="Scale factor applied to the synthetic NOP payload (default: 0.05)",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        default="uint32",
        help="NumPy dtype for the generated tensors (default: uint32)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files under the output directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_dir = generate_assets(
        args.output_dir,
        payload_scale=max(args.payload_scale, 1e-6),
        dtype_name=args.dtype,
        force=args.force,
    )
    print(f"Generated two-layer CNN assets under {output_dir}")


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
