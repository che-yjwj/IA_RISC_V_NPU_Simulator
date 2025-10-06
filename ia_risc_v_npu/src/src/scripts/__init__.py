"""Compatibility wrappers exposing CLI scripts under the ``src.scripts`` namespace."""

from importlib import import_module
from types import ModuleType

__all__ = [
    "cq_vs_elf_benchmark",
    "deterministic_env",
    "regenerate_accuracy_golden",
    "check_specs_index",
]


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        return import_module(f"scripts.{name}")
    raise AttributeError(f"module 'src.scripts' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
