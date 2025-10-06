"""Generate CQ JSONL traces from a YAML plan description."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Tuple

import yaml

from src.cq.io import dump_cq_trace
from src.cq.schema import CommandQueue, CQValidationError
from src.cq.spec import ISASpec, ISASpecError, load_isa_spec


class PlanError(ValueError):
    """Raised when the input plan file cannot be converted into a CQ trace."""


@dataclass(slots=True)
class Plan:
    commands: Tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, Any]


def _ensure_mapping(value: Any, *, field: str) -> MutableMapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise PlanError(f"{field} must be an object")
    result: MutableMapping[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise PlanError(f"{field} keys must be strings")
        result[key] = item
    return result


def _normalise_command(index: int, payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise PlanError(f"commands[{index}] must be an object")

    data = dict(payload)
    if "cmd_id" not in data:
        identifier = data.pop("id", None)
        if identifier is None:
            raise PlanError(f"commands[{index}] is missing 'cmd_id'")
        data["cmd_id"] = identifier

    opcode = data.get("opcode")
    if opcode is None:
        raise PlanError(f"commands[{index}] is missing 'opcode'")

    if "dependencies" in data and "deps" not in data:
        data["deps"] = data.pop("dependencies")

    trace = data.get("trace")
    if trace is not None and not isinstance(trace, Mapping):
        raise PlanError(f"commands[{index}].trace must be an object if provided")

    operands = data.get("operands")
    if operands is not None and not isinstance(operands, Mapping):
        raise PlanError(f"commands[{index}].operands must be an object if provided")

    return data


def _load_plan(path: Path) -> Plan:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - parser edge cases
        raise PlanError(f"Failed to parse YAML plan: {path}") from exc
    except OSError as exc:
        raise PlanError(f"Failed to read plan file: {path}") from exc

    if raw is None:
        raise PlanError("Plan file is empty")
    if not isinstance(raw, Mapping):
        raise PlanError("Plan file must contain a top-level object")

    metadata = dict(_ensure_mapping(raw.get("metadata", {}), field="metadata"))

    commands_raw = raw.get("commands")
    if not isinstance(commands_raw, Iterable) or isinstance(commands_raw, Mapping):
        raise PlanError("Plan file must contain a 'commands' array")

    normalised = []
    for index, entry in enumerate(commands_raw):
        normalised.append(_normalise_command(index, entry))

    return Plan(commands=tuple(normalised), metadata=metadata)


def _validate_with_isa(queue: CommandQueue, spec: ISASpec) -> None:
    issues, _ = spec.validate_queue(queue)
    if issues:
        details = ", ".join(f"{issue.command_id}:{issue.kind}" for issue in issues)
        raise PlanError(f"ISA validation failed: {details}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert CQ plan YAML into JSONL traces compatible with the simulator"
        ),
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Path to the YAML plan"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination path for the generated CQ JSONL file",
    )
    parser.add_argument(
        "--isa",
        type=Path,
        default=None,
        help="Optional ISA spec to validate opcodes and operands",
    )
    parser.add_argument(
        "--allow-forward-deps",
        action="store_true",
        help="Permit dependencies on commands that appear later in the plan",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=None,
        help="If set, emit a formatted preview of the CQ trace to stdout",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    plan = _load_plan(args.input)

    try:
        queue = CommandQueue.from_iterable(
            plan.commands,
            metadata=plan.metadata,
            strict=not args.allow_forward_deps,
        )
    except CQValidationError as exc:
        raise PlanError(str(exc)) from exc

    if args.isa is not None:
        try:
            spec = load_isa_spec(args.isa)
        except ISASpecError as exc:
            raise PlanError(str(exc)) from exc
        _validate_with_isa(queue, spec)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    dump_cq_trace(queue, args.output)

    if args.indent is not None:
        preview: list[dict[str, Any]] = []
        if plan.metadata:
            preview.append({"metadata": dict(plan.metadata)})
        preview.extend(queue.to_list())
        print(json.dumps(preview, indent=args.indent))

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except PlanError as exc:
        parser.error(str(exc))
    return 1


__all__ = ["main", "run", "build_parser", "Plan", "PlanError"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
