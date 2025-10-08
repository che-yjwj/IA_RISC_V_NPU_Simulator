# Auto-generated via scripts/generate_cq_models.py. Do not edit manually.

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple

from src.cq.spec import ISASpecError

if TYPE_CHECKING:
    from src.cq.schema import CQCommand


def _require_operand(command: "CQCommand", operands: dict, name: str) -> Any:
    if name not in operands:
        raise ISASpecError(
            (
                f"Command '{command.cmd_id}' ({command.opcode}) "
                f"operand '{name}' must be present"
            )
        )
    return operands[name]


def _optional_operand(command: "CQCommand", operands: dict, name: str) -> Any | None:
    return operands.get(name)


def _coerce_int(value: Any, command: "CQCommand", name: str) -> int:
    if not isinstance(value, int):
        raise ISASpecError(
            (
                f"Command '{command.cmd_id}' ({command.opcode}) "
                f"operand '{name}' must be an integer"
            )
        )
    return int(value)


def _coerce_float(value: Any, command: "CQCommand", name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ISASpecError(
            (
                f"Command '{command.cmd_id}' ({command.opcode}) "
                f"operand '{name}' must be numeric"
            )
        )
    return float(value)


def _coerce_bool(value: Any, command: "CQCommand", name: str) -> bool:
    if not isinstance(value, bool):
        raise ISASpecError(
            (
                f"Command '{command.cmd_id}' ({command.opcode}) "
                f"operand '{name}' must be boolean"
            )
        )
    return bool(value)


def _coerce_str(value: Any, command: "CQCommand", name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ISASpecError(
            (
                f"Command '{command.cmd_id}' ({command.opcode}) "
                f"operand '{name}' must be a non-empty string"
            )
        )
    return value


def _coerce_any(value: Any, command: "CQCommand", name: str) -> Any:
    return value


def _coerce_tuple(
    element_fn: Callable[[Any, "CQCommand", str], Any],
    length: int,
    value: Any,
    command: "CQCommand",
    name: str,
) -> Tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ISASpecError(
            (
                f"Command '{command.cmd_id}' ({command.opcode}) "
                f"operand '{name}' must be a sequence"
            )
        )
    if len(value) != length:
        raise ISASpecError(
            (
                f"Command '{command.cmd_id}' ({command.opcode}) "
                f"operand '{name}' must contain exactly {length} entries"
            )
        )
    coerced = [
        element_fn(item, command, f"{name}[{index}]")
        for index, item in enumerate(value)
    ]
    return tuple(coerced)


@dataclass(slots=True)
class DMA_2D_Operands:
    src: str
    dst: str
    shape: Tuple[int, int]
    strides: Optional[Tuple[int, int]] = None

    @classmethod
    def from_command(cls, command: "CQCommand") -> "DMA_2D_Operands":
        operands = command.operands
        src_raw = _require_operand(command, operands, "src")
        src = _coerce_str(src_raw, command, "DMA_2D.src")
        dst_raw = _require_operand(command, operands, "dst")
        dst = _coerce_str(dst_raw, command, "DMA_2D.dst")
        shape_raw = _require_operand(command, operands, "shape")
        shape = _coerce_tuple(
            _coerce_int,
            2,
            shape_raw,
            command,
            "DMA_2D.shape",
        )
        strides_raw = _optional_operand(command, operands, "strides")
        if strides_raw is None:
            strides = None
        else:
            strides = _coerce_tuple(
                _coerce_int,
                2,
                strides_raw,
                command,
                "DMA_2D.strides",
            )

        return cls(
            src=src,
            dst=dst,
            shape=shape,
            strides=strides,
        )


@dataclass(slots=True)
class TE_GEMM_Operands:
    m: int
    n: int
    k: int
    a: str
    b: str
    c: Optional[str] = None

    @classmethod
    def from_command(cls, command: "CQCommand") -> "TE_GEMM_Operands":
        operands = command.operands
        m_raw = _require_operand(command, operands, "m")
        m = _coerce_int(m_raw, command, "TE_GEMM.m")
        n_raw = _require_operand(command, operands, "n")
        n = _coerce_int(n_raw, command, "TE_GEMM.n")
        k_raw = _require_operand(command, operands, "k")
        k = _coerce_int(k_raw, command, "TE_GEMM.k")
        a_raw = _require_operand(command, operands, "a")
        a = _coerce_str(a_raw, command, "TE_GEMM.a")
        b_raw = _require_operand(command, operands, "b")
        b = _coerce_str(b_raw, command, "TE_GEMM.b")
        c_raw = _optional_operand(command, operands, "c")
        if c_raw is None:
            c = None
        else:
            c = _coerce_str(c_raw, command, "TE_GEMM.c")

        return cls(
            m=m,
            n=n,
            k=k,
            a=a,
            b=b,
            c=c,
        )


@dataclass(slots=True)
class TE_CONV2D_Operands:
    input: str
    weights: str
    output: str
    stride: Optional[Tuple[int, int]] = None
    padding: Optional[Tuple[int, int]] = None
    dilation: Optional[Tuple[int, int]] = None
    groups: Optional[int] = None

    @classmethod
    def from_command(cls, command: "CQCommand") -> "TE_CONV2D_Operands":
        operands = command.operands
        input_raw = _require_operand(command, operands, "input")
        input = _coerce_str(input_raw, command, "TE_CONV2D.input")
        weights_raw = _require_operand(command, operands, "weights")
        weights = _coerce_str(weights_raw, command, "TE_CONV2D.weights")
        output_raw = _require_operand(command, operands, "output")
        output = _coerce_str(output_raw, command, "TE_CONV2D.output")
        stride_raw = _optional_operand(command, operands, "stride")
        if stride_raw is None:
            stride = None
        else:
            stride = _coerce_tuple(
                _coerce_int,
                2,
                stride_raw,
                command,
                "TE_CONV2D.stride",
            )
        padding_raw = _optional_operand(command, operands, "padding")
        if padding_raw is None:
            padding = None
        else:
            padding = _coerce_tuple(
                _coerce_int,
                2,
                padding_raw,
                command,
                "TE_CONV2D.padding",
            )
        dilation_raw = _optional_operand(command, operands, "dilation")
        if dilation_raw is None:
            dilation = None
        else:
            dilation = _coerce_tuple(
                _coerce_int,
                2,
                dilation_raw,
                command,
                "TE_CONV2D.dilation",
            )
        groups_raw = _optional_operand(command, operands, "groups")
        if groups_raw is None:
            groups = None
        else:
            groups = _coerce_int(groups_raw, command, "TE_CONV2D.groups")

        return cls(
            input=input,
            weights=weights,
            output=output,
            stride=stride,
            padding=padding,
            dilation=dilation,
            groups=groups,
        )


@dataclass(slots=True)
class FENCE_SPM_Operands:
    pass

    @classmethod
    def from_command(cls, command: "CQCommand") -> "FENCE_SPM_Operands":
        return cls()


OPERAND_MODELS = {
    "DMA_2D": DMA_2D_Operands,
    "TE_GEMM": TE_GEMM_Operands,
    "TE_CONV2D": TE_CONV2D_Operands,
    "FENCE_SPM": FENCE_SPM_Operands,
}

__all__ = [
    "DMA_2D_Operands",
    "TE_GEMM_Operands",
    "TE_CONV2D_Operands",
    "FENCE_SPM_Operands",
    "OPERAND_MODELS",
]
