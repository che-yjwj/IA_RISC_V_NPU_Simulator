"""Helpers for loading and validating the simulator ISA specification."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, Mapping, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - import used for typing only
    from .schema import CQCommand

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency check
    raise RuntimeError(
        "PyYAML is required to use the ISA specification helpers. "
        "Install it via 'pip install pyyaml'."
    ) from exc


class ISASpecError(ValueError):
    """Raised when the ISA specification file is invalid or missing."""


@dataclass(slots=True, frozen=True)
class OperandSpec:
    name: str
    type: str
    required: bool = True
    description: str | None = None

    @classmethod
    def from_mapping(cls, name: str, payload: Mapping[str, Any]) -> "OperandSpec":
        if not isinstance(payload, Mapping):
            raise ISASpecError(f"Operand '{name}' must be an object")
        operand_type = payload.get("type")
        if not isinstance(operand_type, str) or not operand_type:
            raise ISASpecError(f"Operand '{name}' requires a non-empty 'type' field")
        required = payload.get("required", True)
        if not isinstance(required, bool):
            raise ISASpecError(
                f"Operand '{name}' field 'required' must be a boolean if present"
            )
        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            raise ISASpecError(
                f"Operand '{name}' field 'description' must be a string if present"
            )
        return cls(
            name=name, type=operand_type, required=required, description=description
        )


@dataclass(slots=True, frozen=True)
class ISAOperation:
    name: str
    category: str
    summary: str
    operands: Dict[str, OperandSpec] = field(default_factory=dict)
    tags: Tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ISAOperation":
        if not isinstance(payload, Mapping):
            raise ISASpecError("Each operation entry must be an object")
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            raise ISASpecError("Operation entry missing 'name'")
        category = payload.get("category", "")
        if not isinstance(category, str) or not category:
            raise ISASpecError(f"Operation '{name}' requires a non-empty 'category'")
        summary = payload.get("summary", "")
        if not isinstance(summary, str) or not summary:
            raise ISASpecError(f"Operation '{name}' requires a non-empty 'summary'")

        operands_payload = payload.get("operands", {})
        if not isinstance(operands_payload, Mapping):
            raise ISASpecError(f"Operation '{name}' field 'operands' must be an object")
        operands: Dict[str, OperandSpec] = {}
        for operand_name, operand_spec in operands_payload.items():
            operands[operand_name] = OperandSpec.from_mapping(
                operand_name, operand_spec
            )

        tags_payload = payload.get("tags", [])
        if not isinstance(tags_payload, Iterable) or isinstance(
            tags_payload, (str, bytes)
        ):
            raise ISASpecError(
                f"Operation '{name}' field 'tags' must be an array of strings"
            )
        tags: list[str] = []
        for tag in tags_payload:
            if not isinstance(tag, str) or not tag:
                raise ISASpecError(
                    "Operation '{name}' has an invalid tag entry "
                    "(must be non-empty string)".format(name=name)
                )
            tags.append(tag)

        return cls(
            name=name,
            category=category,
            summary=summary,
            operands=operands,
            tags=tuple(tags),
        )

    def validate_operands(
        self, operands: Mapping[str, Any]
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        required_missing: list[str] = []
        if not isinstance(operands, Mapping):
            operands = {}
        provided_keys = set(operands.keys())
        for operand in self.operands.values():
            if operand.required and operand.name not in provided_keys:
                required_missing.append(operand.name)
        allowed = set(self.operands.keys())
        unexpected = tuple(sorted(provided_keys - allowed))
        return tuple(sorted(required_missing)), unexpected


@dataclass(slots=True, frozen=True)
class ISAValidationIssue:
    command_id: str
    opcode: str
    kind: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "command_id": self.command_id,
            "opcode": self.opcode,
            "kind": self.kind,
        }
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(slots=True, frozen=True)
class ISASpec:
    version: int
    operations: Dict[str, ISAOperation]

    def get_operation(self, name: str) -> ISAOperation | None:
        return self.operations.get(name)

    def validate_queue(
        self, commands: Iterable["CQCommand"]
    ) -> tuple[list[ISAValidationIssue], set[str]]:
        issues: list[ISAValidationIssue] = []
        seen_opcodes: set[str] = set()
        for command in commands:
            opcode = command.opcode
            operation = self.get_operation(opcode)
            if operation is None:
                issues.append(
                    ISAValidationIssue(
                        command_id=command.cmd_id,
                        opcode=opcode,
                        kind="unknown_opcode",
                    )
                )
                continue
            seen_opcodes.add(opcode)
            missing, unexpected = operation.validate_operands(command.operands)
            if missing:
                issues.append(
                    ISAValidationIssue(
                        command_id=command.cmd_id,
                        opcode=opcode,
                        kind="missing_operands",
                        details={"operands": missing},
                    )
                )
            if unexpected:
                issues.append(
                    ISAValidationIssue(
                        command_id=command.cmd_id,
                        opcode=opcode,
                        kind="unexpected_operands",
                        details={"operands": unexpected},
                    )
                )
        return issues, seen_opcodes


def _resolve_default_spec_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "specs" / "isa.yaml"
        if candidate.exists():
            return candidate
    raise ISASpecError(
        "Unable to locate default ISA specification file (specs/isa.yaml)"
    )


def load_isa_spec(path: Optional[Path] = None) -> ISASpec:
    target = path or _resolve_default_spec_path()
    try:
        with target.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ISASpecError(f"ISA spec file not found: {target}") from exc
    except OSError as exc:
        raise ISASpecError(f"Failed to read ISA spec: {target}") from exc

    if not isinstance(payload, Mapping):
        raise ISASpecError("ISA specification must be a mapping")

    version = payload.get("version")
    if version is None:
        raise ISASpecError("ISA specification missing 'version'")
    if not isinstance(version, int) or version <= 0:
        raise ISASpecError("ISA specification 'version' must be a positive integer")

    operations_payload = payload.get("operations")
    if not isinstance(operations_payload, Iterable):
        raise ISASpecError("ISA specification 'operations' must be a list")

    operations: Dict[str, ISAOperation] = {}
    for entry in operations_payload:
        operation = ISAOperation.from_mapping(entry)
        if operation.name in operations:
            raise ISASpecError(f"Duplicate ISA opcode entry: {operation.name}")
        operations[operation.name] = operation

    if not operations:
        raise ISASpecError("ISA specification must declare at least one operation")

    return ISASpec(version=version, operations=operations)


__all__ = [
    "ISASpec",
    "ISASpecError",
    "ISAValidationIssue",
    "ISAOperation",
    "OperandSpec",
    "load_isa_spec",
]
