"""CQ command adapter translating ISA opcodes into execution plans.

The adapter acts as a bridge between high-level CQ traces and the simulator's
runtime.  It inspects the operands registered in the ISA specification and
returns structured plan objects that downstream components can consume without
having to re-parse the JSON payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping, Optional

from .generated.isa_operands import (
    OPERAND_MODELS,
    DMA_2D_Operands,
    FENCE_SPM_Operands,
    TE_GEMM_Operands,
)
from .schema import CommandQueue
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


def build_execution_plan(queue: CommandQueue, spec: ISASpec) -> CQExecutionPlan:
    plan = CQExecutionPlan(metadata=queue.metadata)
    for command in queue:
        opcode = command.opcode

        operands_cls = OPERAND_MODELS.get(opcode)
        if operands_cls is None:
            if spec.get_operation(opcode) is None:
                raise ISASpecError(f"Opcode '{opcode}' is not declared in ISA spec")
            raise ISASpecError(
                f"Opcode '{opcode}' does not have an adapter implementation yet"
            )

        operands = operands_cls.from_command(command)

        if isinstance(operands, DMA_2D_Operands):
            plan.dma_ops.append(
                DMAPlan(
                    cmd_id=command.cmd_id,
                    src=operands.src,
                    dst=operands.dst,
                    shape=tuple(int(dim) for dim in operands.shape),
                    strides=(
                        tuple(int(dim) for dim in operands.strides)
                        if operands.strides is not None
                        else None
                    ),
                )
            )
        elif isinstance(operands, TE_GEMM_Operands):
            plan.gemm_ops.append(
                GEMMPlan(
                    cmd_id=command.cmd_id,
                    m=int(operands.m),
                    n=int(operands.n),
                    k=int(operands.k),
                    a=operands.a,
                    b=operands.b,
                    c=operands.c,
                )
            )
        elif isinstance(operands, FENCE_SPM_Operands):
            target_value = command.operands.get("target")
            plan.fence_ops.append(
                FencePlan(
                    cmd_id=command.cmd_id,
                    target=str(target_value) if target_value else None,
                )
            )
        else:
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
