"""Re-export specs index checker under ``src.scripts``."""

from importlib import import_module
from types import ModuleType
from typing import Any

_IMPL: ModuleType = import_module("scripts.check_specs_index")

__all__ = ["check_specs_index", "main"]

check_specs_index = _IMPL.check_specs_index
main = _IMPL.main


def __getattr__(name: str) -> Any:  # pragma: no cover - passthrough shim
    return getattr(_IMPL, name)
