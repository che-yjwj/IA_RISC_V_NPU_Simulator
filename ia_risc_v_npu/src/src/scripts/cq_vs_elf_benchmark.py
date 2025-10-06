"""Re-export the CQ vs ELF benchmarking CLI without wildcard imports."""

from importlib import import_module
from types import ModuleType
from typing import Any

_IMPL: ModuleType = import_module("scripts.cq_vs_elf_benchmark")

__all__ = ["build_parser", "main", "_format_report"]

build_parser = _IMPL.build_parser
main = _IMPL.main
_format_report = _IMPL._format_report  # noqa: SLF001 - intentionally surfaced


def __getattr__(name: str) -> Any:  # pragma: no cover - passthrough shim
    return getattr(_IMPL, name)
