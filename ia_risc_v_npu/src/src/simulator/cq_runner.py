"""Helpers for executing CQ traces alongside the existing ELF pipeline.

The functions in this module are intentionally lightweight scaffolding so that
Stage 4 work can bridge the CQ path with the established benchmarking flow.
"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Optional

from src.cq import CommandQueue, load_cq_trace
from src.simulator.cli import load_program_image
from src.simulator.config import (
    ConfigValidationError,
    default_simulator_config,
    validate_simulator_config,
)
from src.simulator.main import AdaptiveSimulator


def _load_config(path: Optional[Path]) -> Mapping[str, Any]:
    if path is None:
        return default_simulator_config()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - file missing guard
        raise FileNotFoundError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file is not valid JSON: {path}") from exc

    try:
        return validate_simulator_config(data)
    except ConfigValidationError as exc:
        raise ValueError(f"Invalid configuration: {exc}") from exc


def compare_cq_vs_elf(
    *,
    cq_trace: Path,
    elf_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Return parallel summaries for CQ and ELF paths.

    The ELF execution is currently a placeholder so that benchmarking harnesses
    can be connected in a later revision without changing the public surface.
    """

    config = _load_config(config_path)

    queue: CommandQueue = load_cq_trace(cq_trace)
    cq_sim = AdaptiveSimulator(config=deepcopy(config))
    cq_summary = cq_sim.run_cq_trace(queue)

    elf_summary: dict[str, Any]
    if elf_path is None:
        elf_summary = {"status": "not_provided"}
    else:
        try:
            elf_program = load_program_image(elf_path)
            elf_sim = AdaptiveSimulator(config=deepcopy(config))
            elf_sim.load_program(elf_program)
            report = asyncio.run(elf_sim.run_simulation())
            elf_summary = {
                "status": "ok",
                "cycles": report.cycles,
                "instructions": report.instructions,
                "mips": report.mips,
                "halted": report.halted,
                "reason": report.reason,
                "elapsed_seconds": report.elapsed_seconds,
                "path": str(elf_path),
            }
        except Exception as exc:  # noqa: BLE001 - propagate status for metrics
            elf_summary = {
                "status": "error",
                "message": str(exc),
                "path": str(elf_path),
            }

    report = {
        "cq_summary": cq_summary,
        "elf_summary": elf_summary,
        "status": (
            "cq_ready_elf_pending" if elf_summary.get("status") != "ok" else "ready"
        ),
    }
    report["cq_trace"] = str(cq_trace)
    return report


__all__ = ["compare_cq_vs_elf"]
