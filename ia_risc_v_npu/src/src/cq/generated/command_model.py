# Auto-generated via scripts/generate_cq_models.py. Do not edit manually.

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, root_validator, validator


class CQCommandModel(BaseModel):
    cmd_id: str
    opcode: str
    operands: Dict[str, Any] = Field(default_factory=dict)
    deps: List[str] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        allow_population_by_field_name = True
        extra = "allow"

    @root_validator(pre=True)
    def _alias_dependencies(
        cls, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        if "deps" not in values and "dependencies" in values:
            values["deps"] = values.pop("dependencies")
        return values

    @validator("cmd_id", "opcode")
    def _require_string(cls, value: str, field) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field.name} must be a non-empty string")
        return value.strip()

    @validator("deps", each_item=True)
    def _deps_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("dependency identifiers must be non-empty strings")
        return value.strip()

    @validator("deps")
    def _deps_unique(cls, values: List[str]) -> List[str]:
        seen = set()
        duplicates = {item for item in values if item in seen or seen.add(item)}
        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise ValueError(f"dependencies contain duplicates: {joined}")
        return values


__all__ = ["CQCommandModel", "ValidationError"]
