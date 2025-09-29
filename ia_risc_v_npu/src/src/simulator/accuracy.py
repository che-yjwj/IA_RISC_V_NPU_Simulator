"""Accuracy guard utilities for comparing simulation outputs to golden baselines."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


class AccuracyGuardError(RuntimeError):
    """Raised when accuracy guard evaluation cannot be completed."""


@dataclass(slots=True)
class AccuracyGuardOutcome:
    """Structured result returned by the accuracy guard."""

    payload: Dict[str, Any]
    passed: bool


def _flatten_numeric(data: Any, prefix: str = "") -> Dict[str, float]:
    items: Dict[str, float] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            items.update(_flatten_numeric(value, new_prefix))
    elif isinstance(data, (int, float)) and prefix:
        items[prefix] = float(data)
    return items


def _resolve_golden_path(golds_path: str, base_path: Path) -> Path:
    path = Path(golds_path)
    if not path.is_absolute():
        path = base_path / path
    return path.resolve()


def _load_golden_metrics(golds_path: Path) -> Dict[str, Any]:
    try:
        with golds_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise AccuracyGuardError(f"Golden reference file not found: {golds_path}") from exc
    except json.JSONDecodeError as exc:
        raise AccuracyGuardError(f"Golden reference file is not valid JSON: {golds_path}") from exc

    if not isinstance(data, dict):
        raise AccuracyGuardError("Golden reference must be a JSON object mapping metrics to values")
    return data


def evaluate_accuracy_guard(
    summary: Dict[str, Any],
    guard_config: Dict[str, Any] | None,
    *,
    base_path: Path,
) -> AccuracyGuardOutcome | None:
    """Evaluate the accuracy guard against the provided ``summary``.

    Args:
        summary: Flattened simulation results (usually produced by ``prepare_summary``).
        guard_config: User configuration block for the guard.
        base_path: Directory used to resolve relative golden file paths.

    Returns:
        ``AccuracyGuardOutcome`` when the guard ran, otherwise ``None`` if disabled.
    """

    if not guard_config or not guard_config.get("enabled", False):
        return None

    golds_path_value = guard_config.get("golds_path")
    if not golds_path_value:
        raise AccuracyGuardError("accuracy_guard.golds_path must be set when the guard is enabled")

    golden_path = _resolve_golden_path(str(golds_path_value), base_path)
    golden_data = _load_golden_metrics(golden_path)

    actual_flat = _flatten_numeric(summary)
    golden_flat = _flatten_numeric(golden_data)

    if not golden_flat:
        raise AccuracyGuardError("Golden reference does not contain numeric metrics to compare")

    max_avg_threshold = float(guard_config.get("max_average_deviation", 0.0))
    max_single_threshold = float(guard_config.get("max_single_deviation", 0.0))

    metrics_report = []
    deviations: list[float] = []
    missing_metrics: list[str] = []

    for metric_name, expected_value in golden_flat.items():
        if metric_name not in actual_flat:
            missing_metrics.append(metric_name)
            continue

        actual_value = actual_flat[metric_name]
        deviation = float("inf")
        if expected_value == 0:
            deviation = 0.0 if actual_value == 0 else float("inf")
        else:
            deviation = abs(actual_value - expected_value) / abs(expected_value)

        deviations.append(deviation)
        metrics_report.append(
            {
                "name": metric_name,
                "expected": expected_value,
                "actual": actual_value,
                "deviation": None if math.isinf(deviation) else deviation,
                "deviation_pct": None if math.isinf(deviation) else deviation * 100,
                "infinite_deviation": math.isinf(deviation),
            }
        )

    if missing_metrics:
        status = "error"
        passed = False
        average_deviation = float("inf")
        max_deviation = float("inf")
    elif not metrics_report:
        status = "error"
        passed = False
        average_deviation = float("inf")
        max_deviation = float("inf")
    else:
        finite_deviations = [value for value in deviations if not math.isinf(value)]
        has_infinite = len(finite_deviations) != len(deviations)
        average_deviation = (
            sum(finite_deviations) / len(finite_deviations) if finite_deviations else float("inf")
        )
        max_deviation = max(deviations) if deviations else 0.0

        passed = (
            not has_infinite
            and average_deviation <= max_avg_threshold
            and max_deviation <= max_single_threshold
        )
        status = "ok" if passed else "failed"

    outcome_payload = {
        "status": status,
        "golds_path": str(golden_path),
        "thresholds": {
            "max_average_deviation": max_avg_threshold,
            "max_single_deviation": max_single_threshold,
        },
        "metrics": metrics_report,
        "average_deviation": None if math.isinf(average_deviation) else average_deviation,
        "average_deviation_pct": None
        if math.isinf(average_deviation)
        else average_deviation * 100,
        "max_deviation": None if math.isinf(max_deviation) else max_deviation,
        "max_deviation_pct": None if math.isinf(max_deviation) else max_deviation * 100,
        "missing_metrics": missing_metrics,
    }

    return AccuracyGuardOutcome(payload=outcome_payload, passed=passed)


__all__ = ["AccuracyGuardError", "AccuracyGuardOutcome", "evaluate_accuracy_guard"]

