"""Re-export the golden regeneration helper under ``src.scripts``."""

from importlib import import_module
from types import ModuleType
from typing import Any

_IMPL: ModuleType = import_module("scripts.regenerate_accuracy_golden")

__all__ = ["regenerate", "main"]

regenerate = _IMPL.regenerate
main = _IMPL.main


def __getattr__(name: str) -> Any:  # pragma: no cover - passthrough shim
    return getattr(_IMPL, name)
