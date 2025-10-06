"""Re-export deterministic environment helpers under ``src.scripts``."""

from importlib import import_module
from types import ModuleType
from typing import Any

_IMPL: ModuleType = import_module("scripts.deterministic_env")

__all__ = [
    "CommandResult",
    "Runner",
    "main",
]

CommandResult = _IMPL.CommandResult
Runner = _IMPL.Runner
main = _IMPL.main


def __getattr__(name: str) -> Any:  # pragma: no cover - passthrough shim
    return getattr(_IMPL, name)
