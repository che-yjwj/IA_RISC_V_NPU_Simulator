"""IR to ISA mapping helpers driven by YAML rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import yaml


class RuleError(ValueError):
    """Raised when a rule set cannot be applied to the provided IR."""


@dataclass(slots=True)
class Rule:
    name: str
    match: Mapping[str, Any]
    emit: Sequence[Mapping[str, Any]]


_TEMPLATE_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
_SIMPLE_TEMPLATE_RE = re.compile(r"^\s*\{\{\s*([^}]+?)\s*\}\}\s*$")


def _default_rules_dir() -> Path:
    return Path(__file__).resolve().parent / "rules"


def _load_rule_payload(path: Path) -> List[Rule]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuleError(f"Failed to parse rule file {path}: {exc}") from exc
    except OSError as exc:
        raise RuleError(f"Failed to read rule file: {path}") from exc

    if not isinstance(data, Mapping):
        raise RuleError(f"Rule file {path} must contain a top-level mapping")
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, Iterable):
        raise RuleError(f"Rule file {path} field 'rules' must be an iterable")

    rules: list[Rule] = []
    for index, entry in enumerate(raw_rules):
        if not isinstance(entry, Mapping):
            raise RuleError(f"Rule entry {index} in {path} must be an object")
        name = entry.get("name") or f"{path.name}:{index}"
        match = entry.get("match", {})
        emit = entry.get("emit", [])
        if not isinstance(match, Mapping):
            raise RuleError(f"Rule {name} match section must be an object")
        if not isinstance(emit, Iterable):
            raise RuleError(f"Rule {name} emit section must be an array")
        rules.append(Rule(name=name, match=dict(match), emit=list(emit)))
    return rules


def load_rules(paths: Sequence[Path] | None = None) -> List[Rule]:
    """Load YAML rule files and return the aggregated rule set."""

    rule_paths: list[Path] = []
    if paths:
        for item in paths:
            if item.is_dir():
                rule_paths.extend(sorted(item.glob("*.yml")))
                rule_paths.extend(sorted(item.glob("*.yaml")))
            else:
                rule_paths.append(item)
    else:
        directory = _default_rules_dir()
        rule_paths.extend(sorted(directory.glob("*.yml")))
        rule_paths.extend(sorted(directory.glob("*.yaml")))

    if not rule_paths:
        raise RuleError("No rule files found")

    rules: list[Rule] = []
    for path in rule_paths:
        rules.extend(_load_rule_payload(path))
    return rules


def _resolve_path(path: str, context: Mapping[str, Any]) -> Any:
    segments = path.split(".")
    current: Any = context
    for segment in segments:
        if isinstance(current, Mapping):
            if segment not in current:
                raise RuleError(
                    f"Context key '{segment}' not found while resolving '{path}'"
                )
            current = current[segment]
        elif isinstance(current, (list, tuple)) and segment.isdigit():
            index = int(segment)
            try:
                current = current[index]
            except IndexError as exc:
                raise RuleError(
                    f"Index {index} out of range while resolving '{path}'"
                ) from exc
        else:
            raise RuleError(f"Cannot resolve segment '{segment}' in path '{path}'")
    return current


def _render_value(value: Any, context: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        simple = _SIMPLE_TEMPLATE_RE.match(value)
        if simple:
            resolved = _resolve_path(simple.group(1).strip(), context)
            return resolved

        def replace(match: re.Match[str]) -> str:
            resolved = _resolve_path(match.group(1).strip(), context)
            return str(resolved)

        return _TEMPLATE_RE.sub(replace, value)
    if isinstance(value, list):
        return [_render_value(item, context) for item in value]
    if isinstance(value, tuple):
        return tuple(_render_value(item, context) for item in value)
    if isinstance(value, Mapping):
        return {key: _render_value(val, context) for key, val in value.items()}
    return value


def _match_rule(rule: Rule, node: Mapping[str, Any]) -> bool:
    for key, expected in rule.match.items():
        actual = node.get(key)
        if actual != expected:
            return False
    return True


def _valid_buffer_name(candidate: object) -> str | None:
    if isinstance(candidate, str) and candidate:
        return candidate
    return None


def _buffer_reads(opcode: str, operands: Mapping[str, Any]) -> list[str]:
    opcode_upper = (opcode or "").upper()
    reads: list[str] = []
    if opcode_upper.startswith("DMA"):
        reads.append(_valid_buffer_name(operands.get("src")))
    elif opcode_upper.startswith("TE_"):
        reads.extend(
            [
                _valid_buffer_name(operands.get("a")),
                _valid_buffer_name(operands.get("b")),
                _valid_buffer_name(operands.get("c")),
            ]
        )
    elif opcode_upper.startswith("VEC_"):
        reads.extend(
            [
                _valid_buffer_name(operands.get("src0")),
                _valid_buffer_name(operands.get("src1")),
            ]
        )
    return [buf for buf in reads if buf is not None]


def _buffer_writes(opcode: str, operands: Mapping[str, Any]) -> list[str]:
    opcode_upper = (opcode or "").upper()
    writes: list[str] = []
    if opcode_upper.startswith("DMA"):
        writes.append(_valid_buffer_name(operands.get("dst")))
    elif opcode_upper.startswith("TE_"):
        writes.append(_valid_buffer_name(operands.get("c")))
    elif opcode_upper.startswith("VEC_"):
        writes.append(_valid_buffer_name(operands.get("dst")))
    return [buf for buf in writes if buf is not None]


def _merge_dependencies(
    existing: Sequence[str], additional: Sequence[str]
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for dep in list(existing) + list(additional):
        if not isinstance(dep, str):
            continue
        if dep in seen:
            continue
        merged.append(dep)
        seen.add(dep)
    return merged


def map_ir_to_isa(
    ir_nodes: Iterable[Mapping[str, Any]],
    *,
    rules: Sequence[Rule] | None = None,
) -> List[Dict[str, Any]]:
    """Return an ordered ISA instruction stream for *ir_nodes*."""

    loaded_rules = list(rules) if rules is not None else load_rules(None)
    if not loaded_rules:
        raise RuleError("Rule set is empty")

    instructions: list[Dict[str, Any]] = []
    for node in ir_nodes:
        if not isinstance(node, Mapping):
            raise RuleError("IR nodes must be mappings")
        node = dict(node)
        node.setdefault("depends_on", [])
        rule = next((item for item in loaded_rules if _match_rule(item, node)), None)
        if rule is None:
            op = node.get("op", "<unknown>")
            raise RuleError(f"No rule found for IR op '{op}'")

        trace_id = node.get("trace_id") or node.get("id")
        context = {"ir": node, "ir_id": node.get("id"), "trace_id": trace_id}

        for emit_entry in rule.emit:
            if not isinstance(emit_entry, Mapping):
                raise RuleError(f"Rule {rule.name} emit entry must be an object")
            rendered = _render_value(emit_entry, context)
            if not isinstance(rendered, Mapping):
                raise RuleError(f"Rule {rule.name} emit entry must render to an object")

            opcode = rendered.get("opcode")
            cmd_id = rendered.get("cmd_id")
            if not isinstance(opcode, str) or not opcode:
                raise RuleError(
                    f"Rule {rule.name} produced a command with invalid opcode: {opcode}"
                )
            if not isinstance(cmd_id, str) or not cmd_id:
                raise RuleError(
                    f"Rule {rule.name} produced a command with invalid cmd_id: {cmd_id}"
                )

            operands = rendered.get("operands", {})
            if operands is None:
                operands = {}
            if not isinstance(operands, Mapping):
                raise RuleError(f"Rule {rule.name} operands must be an object")

            deps = rendered.get("deps") or rendered.get("dependencies") or []
            if isinstance(deps, (str, bytes)):
                deps = [deps]
            elif isinstance(deps, (list, tuple)):
                deps = list(deps)
            elif deps in (None, False):
                deps = []
            else:
                raise RuleError(f"Rule {rule.name} produced invalid deps for {cmd_id}")

            trace = rendered.get("trace") or {}
            if not isinstance(trace, Mapping):
                raise RuleError(f"Rule {rule.name} trace must be an object")
            trace = dict(trace)
            trace.setdefault("ir_id", trace_id)

            command = {
                "cmd_id": cmd_id,
                "opcode": opcode,
                "operands": dict(operands),
                "deps": list(deps),
                "trace": trace,
            }
            instructions.append(command)

    last_writers: dict[str, tuple[str, str]] = {}
    for command in instructions:
        operands = command.get("operands", {})
        opcode = (command.get("opcode", "") or "").upper()
        existing_deps = command.get("deps", [])
        reads = _buffer_reads(opcode, operands)
        writes = _buffer_writes(opcode, operands)
        is_vector_op = opcode.startswith("VEC_")

        inherited: list[str] = []
        for buffer in reads:
            writer = last_writers.get(buffer)
            if writer and (is_vector_op or writer[1].startswith("VEC_")):
                inherited.append(writer[0])
        for buffer in writes:
            writer = last_writers.get(buffer)
            if writer and (is_vector_op or writer[1].startswith("VEC_")):
                inherited.append(writer[0])

        command["deps"] = _merge_dependencies(existing_deps, inherited)
        for buffer in writes:
            last_writers[buffer] = (command["cmd_id"], opcode)

    for index, command in enumerate(instructions):
        trace = command.setdefault("trace", {})
        if isinstance(trace, Mapping):
            trace.setdefault("isa_idx", index)
        else:  # pragma: no cover - defensive
            command["trace"] = {"isa_idx": index}

    return instructions


__all__ = ["Rule", "RuleError", "load_rules", "map_ir_to_isa"]
