"""Trace chain helpers for CQ command sequences.

These utilities provide a stable way to correlate simulator commands back to
their originating IR operations by tracking a chain of identifiers:

    ir_id → isa_idx → cmd_id

The intent is to keep the core data structures lightweight while still exposing
query helpers that downstream tooling (dispatchers, debuggers, visualisers)
can reuse without having to reimplement the bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

from .schema import CommandQueue, CQCommand, CQValidationError


@dataclass(slots=True, frozen=True)
class TraceLink:
    """Single link in the trace chain for a CQ command."""

    cmd_id: str
    isa_idx: int
    ir_id: Optional[str]
    trace: Mapping[str, object]


@dataclass(slots=True, frozen=True)
class TraceIndex:
    """Bidirectional index for trace links."""

    by_cmd: Mapping[str, TraceLink]
    by_isa_idx: Tuple[TraceLink, ...]
    by_ir: Mapping[str, Tuple[TraceLink, ...]]

    def for_command(self, cmd_id: str) -> Optional[TraceLink]:
        """Return the trace link associated with *cmd_id* if present."""

        return self.by_cmd.get(cmd_id)

    def for_ir(self, ir_id: str) -> Tuple[TraceLink, ...]:
        """Return the ordered trace links derived from *ir_id*."""

        return self.by_ir.get(ir_id, tuple())

    def __len__(self) -> int:
        return len(self.by_cmd)


def _extract_trace_data(command: CQCommand, fallback_idx: int) -> TraceLink:
    """Normalise trace metadata for *command*."""

    raw_trace = dict(command.trace)
    isa_idx_value = raw_trace.get("isa_idx", fallback_idx)
    if not isinstance(isa_idx_value, int):
        raise CQValidationError(
            f"command '{command.cmd_id}' trace field 'isa_idx' must be an integer"
        )
    ir_id_value = raw_trace.get("ir_id")
    if ir_id_value is not None:
        if not isinstance(ir_id_value, str) or not ir_id_value.strip():
            raise CQValidationError(
                f"command '{command.cmd_id}' trace field 'ir_id' "
                "must be a non-empty string"
            )
        ir_id_value = ir_id_value.strip()

    # Preserve the raw trace payload so that additional metadata remains available.
    raw_trace.setdefault("isa_idx", isa_idx_value)
    if ir_id_value is not None:
        raw_trace["ir_id"] = ir_id_value

    return TraceLink(
        cmd_id=command.cmd_id,
        isa_idx=isa_idx_value,
        ir_id=ir_id_value,
        trace=raw_trace,
    )


def build_trace_index(queue: CommandQueue) -> TraceIndex:
    """Return a `TraceIndex` that relates commands to their IR identifiers."""

    links: list[TraceLink] = []
    seen_cmds: set[str] = set()
    seen_isa: Dict[int, str] = {}

    for position, command in enumerate(queue):
        if command.cmd_id in seen_cmds:
            raise CQValidationError(f"duplicate command id in trace: {command.cmd_id}")
        seen_cmds.add(command.cmd_id)

        link = _extract_trace_data(command, position)
        duplicate = seen_isa.get(link.isa_idx)
        if duplicate is not None:
            raise CQValidationError(
                "duplicate isa_idx detected between commands "
                f"'{duplicate}' and '{command.cmd_id}'"
            )
        seen_isa[link.isa_idx] = command.cmd_id
        links.append(link)

    links.sort(key=lambda entry: entry.isa_idx)

    by_cmd: Dict[str, TraceLink] = {link.cmd_id: link for link in links}
    by_ir: Dict[str, list[TraceLink]] = {}
    for link in links:
        if link.ir_id is None:
            continue
        by_ir.setdefault(link.ir_id, []).append(link)

    frozen_by_ir: Dict[str, Tuple[TraceLink, ...]] = {
        ir_id: tuple(entries) for ir_id, entries in by_ir.items()
    }

    return TraceIndex(
        by_cmd=by_cmd,
        by_isa_idx=tuple(links),
        by_ir=frozen_by_ir,
    )


__all__ = ["TraceIndex", "TraceLink", "build_trace_index"]
