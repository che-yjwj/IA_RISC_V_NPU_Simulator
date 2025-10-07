"""Generate CQ helper modules from ISA spec and CQ schema."""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "ia_risc_v_npu" / "src" / "src"
GENERATED_ROOT = SRC_ROOT / "cq" / "generated"
ISA_SPEC_PATH = REPO_ROOT / "specs" / "isa.yaml"
CQ_SCHEMA_PATH = SRC_ROOT / "cq" / "cq.schema.json"


TYPE_MAPPING = {
    "int": "int",
    "integer": "int",
    "float": "float",
    "double": "float",
    "bool": "bool",
    "boolean": "bool",
    "string": "str",
    "str": "str",
    "address": "str",
    "uri": "str",
}


def _load_yaml(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a mapping at the top level")
    return data


def _load_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a JSON object at the top level")
    return data


def _class_name(opcode: str) -> str:
    return f"{opcode}_Operands"


def _python_type(spec_type: str) -> tuple[str, set[str]]:
    spec_type = spec_type.strip()
    if spec_type.endswith("]") and "[" in spec_type:
        base, _, length = spec_type.partition("[")
        if length.endswith("]") and length[:-1].isdigit():
            inner_type, imports = _python_type(base)
            imports.add("Tuple")
            count = int(length[:-1])
            tuple_items = ", ".join(inner_type for _ in range(count))
            return f"Tuple[{tuple_items}]", imports
    mapped = TYPE_MAPPING.get(spec_type.lower(), "Any")
    imports: set[str] = set()
    if mapped == "Any":
        imports.add("Any")
    return mapped, imports


def _coerce_function(annotation: str) -> tuple[str, set[str]]:
    mapping = {
        "int": "_coerce_int",
        "float": "_coerce_float",
        "bool": "_coerce_bool",
        "str": "_coerce_str",
    }
    if annotation.startswith("Tuple["):
        inner = annotation[len("Tuple[") : -1]
        element = inner.split(",")[0].strip() if inner else "Any"
        func, imports = _coerce_function(element)
        imports.add("Tuple")
        return func, imports
    func = mapping.get(annotation, "_coerce_any")
    imports: set[str] = set()
    if annotation == "Any":
        imports.add("Any")
    return func, imports


def _render_operand(
    opcode: str, operand_name: str, operand_type: str, required: bool
) -> tuple[str, list[str], set[str]]:
    annotation, type_imports = _python_type(operand_type)
    func, coercer_imports = _coerce_function(annotation)

    field_annotation = annotation
    if annotation.startswith("Tuple["):
        type_imports.add("Tuple")
    if not required:
        field_annotation = f"Optional[{annotation}]"
        type_imports.add("Optional")
    field_line = f"    {operand_name}: {field_annotation}"
    if not required:
        field_line += " = None"

    value_var = f"{operand_name}_raw"
    accessor = "_require_operand" if required else "_optional_operand"
    context = f"{opcode}.{operand_name}"

    lines: list[str] = [
        f"{value_var} = {accessor}(command, operands, '{operand_name}')"
    ]
    if annotation.startswith("Tuple["):
        tuple_len = annotation.count(",") + 1
        tuple_call = (
            f"_coerce_tuple({func}, {tuple_len}, {value_var}, command, '{context}')"
        )
        if required:
            lines.append(f"{operand_name} = {tuple_call}")
        else:
            lines.extend(
                [
                    f"if {value_var} is None:",
                    f"    {operand_name} = None",
                    "else:",
                    f"    {operand_name} = {tuple_call}",
                ]
            )
    else:
        coerce_call = f"{func}({value_var}, command, '{context}')"
        if required:
            lines.append(f"{operand_name} = {coerce_call}")
        else:
            lines.extend(
                [
                    f"if {value_var} is None:",
                    f"    {operand_name} = None",
                    "else:",
                    f"    {operand_name} = {coerce_call}",
                ]
            )

    imports = type_imports | coercer_imports
    return field_line, lines, imports


def _generate_operands_module(spec: Mapping[str, Any]) -> str:
    operations = spec.get("operations", [])
    if not isinstance(operations, Iterable):
        raise ValueError("ISA spec 'operations' must be an iterable")

    class_blocks: list[list[str]] = []
    class_names: list[str] = []
    imports: set[str] = {"Any", "Callable"}

    for entry in operations:
        if not isinstance(entry, Mapping):
            continue
        opcode = entry.get("name")
        if not isinstance(opcode, str):
            continue
        class_name = _class_name(opcode)
        class_names.append(class_name)

        operands = entry.get("operands", {})
        if not isinstance(operands, Mapping):
            operands = {}

        field_lines: list[str] = []
        extractor_blocks: list[list[str]] = []
        operand_order: list[str] = []

        for operand_name, operand_spec in operands.items():
            if not isinstance(operand_spec, Mapping):
                continue
            operand_type = str(operand_spec.get("type", "object"))
            required = bool(operand_spec.get("required", True))
            field_line, block, needed_imports = _render_operand(
                opcode, operand_name, operand_type, required
            )
            field_lines.append(field_line)
            extractor_blocks.append(block)
            operand_order.append(operand_name)
            imports |= needed_imports

        class_lines: list[str] = ["@dataclass(slots=True)", f"class {class_name}:"]
        if field_lines:
            class_lines.extend(field_lines)
        else:
            class_lines.append("    pass")

        class_lines.extend(
            [
                "",
                "    @classmethod",
                f'    def from_command(cls, command: "CQCommand") -> "{class_name}":',
                "        operands = command.operands",
            ]
        )
        for block in extractor_blocks:
            for line in block:
                class_lines.append(f"        {line}")
        if operand_order:
            class_lines.append("")
            class_lines.append("        return cls(")
            for name in operand_order:
                class_lines.append(f"            {name}={name},")
            class_lines.append("        )")
        else:
            class_lines.append("        return cls()")

        class_blocks.append(class_lines)

    helper_imports = ", ".join(sorted(imports))
    header_lines = [
        "# Auto-generated via scripts/generate_cq_models.py. Do not edit manually.",
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        f"from typing import {helper_imports}",
        "",
        "from src.cq.spec import ISASpecError",
        "",
        "from typing import TYPE_CHECKING",
        "",
        "if TYPE_CHECKING:",
        "    from src.cq.schema import CQCommand",
        "",
        "",
        'def _require_operand(command: "CQCommand", operands: dict, name: str) -> Any:',
        "    if name not in operands:",
        "        raise ISASpecError(",
        "            f\"Command '{command.cmd_id}' ({command.opcode}) operand '{name}' must be present\"",
        "        )",
        "    return operands[name]",
        "",
        "",
        'def _optional_operand(command: "CQCommand", operands: dict, name: str) -> Any | None:',
        "    return operands.get(name)",
        "",
        "",
        'def _coerce_int(value: Any, command: "CQCommand", name: str) -> int:',
        "    if not isinstance(value, int):",
        "        raise ISASpecError(",
        "            f\"Command '{command.cmd_id}' ({command.opcode}) operand '{name}' must be an integer\"",
        "        )",
        "    return int(value)",
        "",
        "",
        'def _coerce_float(value: Any, command: "CQCommand", name: str) -> float:',
        "    if not isinstance(value, (int, float)):",
        "        raise ISASpecError(",
        "            f\"Command '{command.cmd_id}' ({command.opcode}) operand '{name}' must be numeric\"",
        "        )",
        "    return float(value)",
        "",
        "",
        'def _coerce_bool(value: Any, command: "CQCommand", name: str) -> bool:',
        "    if not isinstance(value, bool):",
        "        raise ISASpecError(",
        "            f\"Command '{command.cmd_id}' ({command.opcode}) operand '{name}' must be boolean\"",
        "        )",
        "    return bool(value)",
        "",
        "",
        'def _coerce_str(value: Any, command: "CQCommand", name: str) -> str:',
        "    if not isinstance(value, str) or not value:",
        "        raise ISASpecError(",
        "            f\"Command '{command.cmd_id}' ({command.opcode}) operand '{name}' must be a non-empty string\"",
        "        )",
        "    return value",
        "",
        "",
        'def _coerce_any(value: Any, command: "CQCommand", name: str) -> Any:',
        "    return value",
        "",
        "",
        "def _coerce_tuple(",
        '    element_fn: Callable[[Any, "CQCommand", str], Any],',
        "    length: int,",
        "    value: Any,",
        '    command: "CQCommand",',
        "    name: str,",
        ") -> Tuple[Any, ...]:",
        "    if not isinstance(value, (list, tuple)):",
        "        raise ISASpecError(",
        "            f\"Command '{command.cmd_id}' ({command.opcode}) operand '{name}' must be a sequence\"",
        "        )",
        "    if len(value) != length:",
        "        raise ISASpecError(",
        "            f\"Command '{command.cmd_id}' ({command.opcode}) operand '{name}' must contain exactly {length} entries\"",
        "        )",
        "    coerced = [",
        '        element_fn(item, command, f"{name}[{index}]")',
        "        for index, item in enumerate(value)",
        "    ]",
        "    return tuple(coerced)",
    ]

    body = ["\n".join(lines) for lines in class_blocks]

    mapping_lines = [f'    "{name[:-9]}": {name},' for name in class_names]
    footer_lines = [
        "OPERAND_MODELS = {",
        *mapping_lines,
        "}",
        "",
        "__all__ = [",
        *(f'    "{name}",' for name in class_names),
        '    "OPERAND_MODELS",',
        "]",
    ]

    return "\n\n".join(["\n".join(header_lines), *body, "\n".join(footer_lines)])


def _generate_command_model(schema: Mapping[str, Any]) -> str:
    _ = schema
    lines = [
        "# Auto-generated via scripts/generate_cq_models.py. Do not edit manually.",
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any, Dict, List, Optional",
        "",
        "from pydantic import BaseModel, Field, ValidationError, root_validator, validator",
        "",
        "",
        "class CQCommandModel(BaseModel):",
        "    cmd_id: str",
        "    opcode: str",
        "    operands: Dict[str, Any] = Field(default_factory=dict)",
        "    deps: List[str] = Field(default_factory=list)",
        "    trace: Dict[str, Any] = Field(default_factory=dict)",
        "",
        "    class Config:",
        "        allow_population_by_field_name = True",
        '        extra = "allow"',
        "",
        "    @root_validator(pre=True)",
        "    def _alias_dependencies(",
        "        cls, values: Dict[str, Any]",
        "    ) -> Dict[str, Any]:",
        '        if "deps" not in values and "dependencies" in values:',
        '            values["deps"] = values.pop("dependencies")',
        "        return values",
        "",
        '    @validator("cmd_id", "opcode")',
        "    def _require_string(cls, value: str, field) -> str:",
        "        if not isinstance(value, str) or not value.strip():",
        '            raise ValueError(f"{field.name} must be a non-empty string")',
        "        return value.strip()",
        "",
        '    @validator("deps", each_item=True)',
        "    def _deps_non_empty(cls, value: str) -> str:",
        "        if not isinstance(value, str) or not value.strip():",
        '            raise ValueError("dependency identifiers must be non-empty strings")',
        "        return value.strip()",
        "",
        '    @validator("deps")',
        "    def _deps_unique(cls, values: List[str]) -> List[str]:",
        "        seen = set()",
        "        duplicates = {item for item in values if item in seen or seen.add(item)}",
        "        if duplicates:",
        '            joined = ", ".join(sorted(duplicates))',
        '            raise ValueError(f"dependencies contain duplicates: {joined}")',
        "        return values",
        "",
        "",
        '__all__ = ["CQCommandModel", "ValidationError"]',
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate CQ helper modules")
    parser.add_argument(
        "--isa", type=Path, default=ISA_SPEC_PATH, help="Path to specs/isa.yaml"
    )
    parser.add_argument(
        "--schema", type=Path, default=CQ_SCHEMA_PATH, help="Path to cq.schema.json"
    )
    args = parser.parse_args(argv)

    spec = _load_yaml(args.isa)
    schema = _load_json(args.schema)

    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    (GENERATED_ROOT / "isa_operands.py").write_text(
        _generate_operands_module(spec), encoding="utf-8"
    )
    (GENERATED_ROOT / "command_model.py").write_text(
        _generate_command_model(schema), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
