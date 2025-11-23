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
    VectorAddPlan,
    build_execution_plan,
)
from .dispatcher import (
    CQDispatcher,
    DispatchOutcome,
    DispatchStats,
    DispatchTrace,
    SchedulingPolicy,
    replay_dependencies,
)
from .generated.command_model import CQCommandModel
from .generated.isa_operands import OPERAND_MODELS
from .generator import generate_command_queue
from .io import dump_cq_trace, load_cq_trace
from .mapper import Rule, RuleError, load_rules, map_ir_to_isa
from .models import (
    BusTimingModel,
    DMATimingModel,
    DMATransferPlan,
    ScratchpadTimingModel,
    TensorEngineTimingModel,
)
from .schema import CommandQueue, CQCommand, CQValidationError
from .spec import (
    ISAOperation,
    ISASpec,
    ISASpecError,
    ISAValidationIssue,
    OperandSpec,
    load_isa_spec,
)
from .trace import TraceIndex, TraceLink, build_trace_index

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
    "SchedulingPolicy",
    "replay_dependencies",
    "CQExecutionPlan",
    "DMAPlan",
    "GEMMPlan",
    "VectorAddPlan",
    "FencePlan",
    "build_execution_plan",
    "tools",
    "TraceIndex",
    "TraceLink",
    "build_trace_index",
    "generate_command_queue",
    "load_rules",
    "map_ir_to_isa",
    "Rule",
    "RuleError",
    "BusTimingModel",
    "DMATimingModel",
    "DMATransferPlan",
    "ScratchpadTimingModel",
    "TensorEngineTimingModel",
    "CQCommandModel",
    "OPERAND_MODELS",
]
