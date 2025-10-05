"""CQ command adapter translating ISA opcodes into execution plans.

The adapter acts as a bridge between high-level CQ traces and the simulator's
runtime.  It inspects the operands registered in the ISA specification and
returns structured plan objects that downstream components can consume without
having to re-parse the JSON payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional

from .schema import CommandQueue, CQCommand
from .spec import ISASpec, ISASpecError


@dataclass(slots=True)
class DMAPlan:
    cmd_id: str
    src: str
    dst: str
    shape: tuple[int, int]
    strides: tuple[int, int] | None


@dataclass(slots=True)
class GEMMPlan:
    cmd_id: str
    m: int
    n: int
    k: int
    a: str
    b: str
    c: Optional[str]


@dataclass(slots=True)
class FencePlan:
    cmd_id: str
    target: str | None = None


@dataclass(slots=True)
class CQExecutionPlan:
    dma_ops: List[DMAPlan] = field(default_factory=list)
    gemm_ops: List[GEMMPlan] = field(default_factory=list)
    fence_ops: List[FencePlan] = field(default_factory=list)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "dma": len(self.dma_ops),
            "gemm": len(self.gemm_ops),
            "fence": len(self.fence_ops),
        }


def _require_operand(command: CQCommand, name: str) -> object:
    if name not in command.operands:
        raise ISASpecError(
            "Command '{cmd}' ({opcode}) missing required operand '{operand}'".format(
                cmd=command.cmd_id,
                opcode=command.opcode,
                operand=name,
            )
        )
    return command.operands[name]


def _ensure_int(value: object, *, context: str) -> int:
    if not isinstance(value, int):
        raise ISASpecError(f"Operand '{context}' must be an integer")
    return value


def _ensure_sequence(value: object, *, context: str, length: int) -> tuple[int, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ISASpecError(
            f"Operand '{context}' must be an iterable of length {length}"
        )
    items = tuple(value)
    if len(items) != length:
        raise ISASpecError(f"Operand '{context}' must contain exactly {length} entries")
    result: list[int] = []
    for index, item in enumerate(items):
        if not isinstance(item, int):
            raise ISASpecError(f"Operand '{context}' entry {index} must be an integer")
        result.append(int(item))
    return tuple(result)


def build_execution_plan(queue: CommandQueue, spec: ISASpec) -> CQExecutionPlan:
    plan = CQExecutionPlan(metadata=queue.metadata)
    for command in queue:
        opcode = command.opcode
        if opcode == "DMA_2D":
            src = str(_require_operand(command, "src"))
            dst = str(_require_operand(command, "dst"))
            shape_raw = _require_operand(command, "shape")
            shape = _ensure_sequence(shape_raw, context="shape", length=2)
            strides_raw = command.operands.get("strides")
            strides = (
                _ensure_sequence(strides_raw, context="strides", length=2)
                if strides_raw is not None
                else None
            )
            plan.dma_ops.append(
                DMAPlan(
                    cmd_id=command.cmd_id,
                    src=src,
                    dst=dst,
                    shape=(int(shape[0]), int(shape[1])),
                    strides=(
                        (int(strides[0]), int(strides[1]))
                        if strides is not None
                        else None
                    ),
                )
            )
        elif opcode == "TE_GEMM":
            m = _ensure_int(_require_operand(command, "m"), context="m")
            n = _ensure_int(_require_operand(command, "n"), context="n")
            k = _ensure_int(_require_operand(command, "k"), context="k")
            a = str(_require_operand(command, "a"))
            b = str(_require_operand(command, "b"))
            c_operand = command.operands.get("c")
            c_addr = str(c_operand) if c_operand is not None else None
            plan.gemm_ops.append(
                GEMMPlan(
                    cmd_id=command.cmd_id,
                    m=m,
                    n=n,
                    k=k,
                    a=a,
                    b=b,
                    c=c_addr,
                )
            )
        elif opcode == "FENCE_SPM":
            target = command.operands.get("target")
            plan.fence_ops.append(
                FencePlan(cmd_id=command.cmd_id, target=str(target) if target else None)
            )
        else:
            # Ensure the opcode exists in the spec to surface meaningful errors.
            if spec.get_operation(opcode) is None:
                raise ISASpecError(f"Opcode '{opcode}' is not declared in ISA spec")
            raise ISASpecError(
                f"Opcode '{opcode}' does not have an adapter implementation yet"
            )
    return plan


__all__ = [
    "CQExecutionPlan",
    "DMAPlan",
    "GEMMPlan",
    "FencePlan",
    "build_execution_plan",
]
