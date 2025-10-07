"""Utilities for converting IR graphs into CQ command queues."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from .mapper import Rule, load_rules, map_ir_to_isa
from .schema import CommandQueue


def generate_command_queue(
    ir_graph: Iterable[Mapping[str, Any]],
    *,
    metadata: Optional[Mapping[str, Any]] = None,
    rules: Optional[Iterable[Rule]] = None,
    rules_path: Optional[Path] = None,
) -> CommandQueue:
    """Return a `CommandQueue` generated from *ir_graph*.

    Args:
        ir_graph: Iterable describing the IR nodes to transform.
        metadata: Optional CQ metadata to attach to the queue.
        rules: Pre-loaded rules to use. When provided, *rules_path* is ignored.
        rules_path: Directory or file path(s) containing rule definitions.
    """

    active_rules = list(rules) if rules is not None else None
    if active_rules is None:
        paths = None
        if rules_path is not None:
            paths = [rules_path]
        active_rules = load_rules(paths)

    isa_sequence = map_ir_to_isa(ir_graph, rules=active_rules)
    commands = []
    for entry in isa_sequence:
        command = {
            "cmd_id": entry["cmd_id"],
            "opcode": entry["opcode"],
            "operands": dict(entry.get("operands", {})),
            "deps": list(entry.get("deps", [])),
            "trace": dict(entry.get("trace", {})),
        }
        commands.append(command)

    return CommandQueue.from_iterable(commands, metadata=metadata, strict=True)


__all__ = ["generate_command_queue"]
