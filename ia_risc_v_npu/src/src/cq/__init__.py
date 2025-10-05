"""CQ (Command Queue) trace helpers for the IA RISC-V + NPU simulator.

The package currently exposes lightweight dataclasses and IO utilities for the
upcoming CQ execution path.  The goal is to keep the API surface area stable so
that simulator components can integrate against it incrementally while Stage 4
of the refactoring plan is implemented.
"""

from .adapter import (
    CQExecutionPlan,
    DMAPlan,
    FencePlan,
    GEMMPlan,
    build_execution_plan,
)
from .dispatcher import (
    CQDispatcher,
    DispatchOutcome,
    DispatchStats,
    DispatchTrace,
    replay_dependencies,
)
from .io import dump_cq_trace, load_cq_trace
from .schema import CommandQueue, CQCommand, CQValidationError
from .spec import (
    ISAOperation,
    ISASpec,
    ISASpecError,
    ISAValidationIssue,
    OperandSpec,
    load_isa_spec,
)

__all__ = [
    "CQCommand",
    "CommandQueue",
    "CQValidationError",
    "ISAOperation",
    "ISASpec",
    "ISASpecError",
    "ISAValidationIssue",
    "OperandSpec",
    "load_cq_trace",
    "dump_cq_trace",
    "load_isa_spec",
    "CQDispatcher",
    "DispatchOutcome",
    "DispatchStats",
    "DispatchTrace",
    "replay_dependencies",
    "CQExecutionPlan",
    "DMAPlan",
    "GEMMPlan",
    "FencePlan",
    "build_execution_plan",
]
