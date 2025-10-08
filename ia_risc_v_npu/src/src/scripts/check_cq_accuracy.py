"""Re-export the CQ accuracy guard checker for entry-point compatibility."""

from importlib import import_module
from types import ModuleType
from typing import Any

_IMPL: ModuleType = import_module("scripts.check_cq_accuracy")

__all__ = ["main", "run", "evaluate_workload", "build_parser"]

main = _IMPL.main
run = _IMPL.run
evaluate_workload = _IMPL.evaluate_workload
build_parser = _IMPL.build_parser


def __getattr__(name: str) -> Any:  # pragma: no cover - passthrough shim
    return getattr(_IMPL, name)
