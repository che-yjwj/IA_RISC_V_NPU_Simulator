"""CQ schema primitives used by the command-queue pipeline.

These helpers intentionally avoid third-party runtime validation libraries so
that the simulator keeps a minimal dependency footprint.  The dataclasses offer
`from_dict` constructors that enforce basic type and content checks while
preserving unknown attributes for future extensions of the schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Tuple,
)

if TYPE_CHECKING:
    from .trace import TraceIndex


class CQValidationError(ValueError):
    """Raised when a CQ payload fails basic schema validation."""


def _ensure_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise CQValidationError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise CQValidationError(f"{field_name} cannot be empty")
    return cleaned


def _ensure_str_sequence(value: Any, *, field_name: str) -> Tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):  # allow single string for convenience
        return (_ensure_str(value, field_name=field_name),)
    if not isinstance(value, Iterable):
        raise CQValidationError(f"{field_name} must be a sequence of strings")
    result = []
    for item in value:
        result.append(_ensure_str(item, field_name=field_name))
    return tuple(result)


def _ensure_mapping(value: Any, *, field_name: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise CQValidationError(f"{field_name} must be an object")
    result: Dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise CQValidationError(f"{field_name} keys must be strings")
        result[key] = item
    return result


@dataclass(slots=True)
class CQCommand:
    """Single CQ command with loosely-typed payload fields."""

    cmd_id: str
    opcode: str
    operands: Dict[str, Any] = field(default_factory=dict)
    dependencies: Tuple[str, ...] = field(default_factory=tuple)
    trace: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        strict: bool = True,
    ) -> "CQCommand":
        """Create a `CQCommand` from a JSON-compatible mapping.

        Unknown keys are stored under `attributes` so that experimental fields
        are not lost during round-trips.  When `strict` is set to ``True``,
        duplicate dependency references or invalid field types raise
        `CQValidationError`.
        """

        if not isinstance(payload, Mapping):
            raise CQValidationError("CQ command must be represented as an object")

        working: Dict[str, Any] = dict(payload)
        cmd_id = _ensure_str(working.pop("cmd_id", None), field_name="cmd_id")
        opcode = _ensure_str(working.pop("opcode", None), field_name="opcode")

        deps_key = "deps" if "deps" in working else "dependencies"
        dependencies = _ensure_str_sequence(
            working.pop(deps_key, ()), field_name="dependencies"
        )

        operands = _ensure_mapping(working.pop("operands", {}), field_name="operands")
        trace = _ensure_mapping(working.pop("trace", {}), field_name="trace")

        # Preserve remaining keys for forward compatibility.
        attributes = dict(working)
        if strict:
            duplicate_deps = _find_duplicates(dependencies)
            if duplicate_deps:
                dup_str = ", ".join(sorted(duplicate_deps))
                raise CQValidationError(f"dependencies contain duplicates: {dup_str}")

        return cls(
            cmd_id=cmd_id,
            opcode=opcode,
            operands=operands,
            dependencies=dependencies,
            trace=trace,
            attributes=attributes,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable mapping for the command."""

        payload: Dict[str, Any] = {
            "cmd_id": self.cmd_id,
            "opcode": self.opcode,
        }
        if self.operands:
            payload["operands"] = dict(self.operands)
        if self.dependencies:
            payload["deps"] = list(self.dependencies)
        if self.trace:
            payload["trace"] = dict(self.trace)
        payload.update(self.attributes)
        return payload


def _find_duplicates(items: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        else:
            seen.add(item)
    return duplicates


@dataclass(slots=True)
class CommandQueue:
    """Container that aggregates commands and optional metadata."""

    commands: Tuple[CQCommand, ...]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_iterable(
        cls,
        commands: Iterable[Mapping[str, Any]],
        *,
        metadata: Optional[Mapping[str, Any]] = None,
        strict: bool = True,
    ) -> "CommandQueue":
        parsed: list[CQCommand] = []
        seen_ids: set[str] = set()
        for raw in commands:
            command = CQCommand.from_dict(raw, strict=strict)
            if command.cmd_id in seen_ids:
                raise CQValidationError(
                    f"duplicate command id detected: {command.cmd_id}"
                )
            seen_ids.add(command.cmd_id)
            parsed.append(command)

        if strict:
            missing: Dict[str, set[str]] = {}
            available_ids = {cmd.cmd_id for cmd in parsed}
            for command in parsed:
                unresolved = set(command.dependencies) - available_ids
                if unresolved:
                    missing[command.cmd_id] = unresolved
            if missing:
                formatted = "; ".join(
                    f"{cmd}->[{', '.join(sorted(deps))}]"
                    for cmd, deps in missing.items()
                )
                raise CQValidationError(
                    f"dependencies reference unknown commands: {formatted}"
                )

        meta = _ensure_mapping(metadata, field_name="metadata") if metadata else {}
        return cls(commands=tuple(parsed), metadata=meta)

    def __iter__(self) -> Iterator[CQCommand]:
        return iter(self.commands)

    def __len__(self) -> int:  # pragma: no cover - trivial proxy
        return len(self.commands)

    def command_ids(self) -> Tuple[str, ...]:
        return tuple(command.cmd_id for command in self.commands)

    def to_list(self) -> list[Dict[str, Any]]:
        return [command.to_dict() for command in self.commands]

    def trace_index(self) -> TraceIndex:
        """Build and return a `TraceIndex` for this queue."""

        from .trace import build_trace_index

        return build_trace_index(self)


__all__ = ["CQValidationError", "CQCommand", "CommandQueue"]
