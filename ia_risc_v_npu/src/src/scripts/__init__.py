"""Compatibility wrappers exposing CLI scripts under the ``src.scripts`` namespace."""

from importlib import import_module
from types import ModuleType
from typing import Dict

__all__ = [
    "cq_vs_elf_benchmark",
    "deterministic_env",
]


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        return import_module(f"scripts.{name}")
    raise AttributeError(f"module 'src.scripts' has no attribute '{name}'")


def __dir__() -> Dict[str, str]:
    return sorted(set(globals()) | set(__all__))
