from pathlib import Path

import json

import pytest

from src.simulator.accuracy import AccuracyGuardError, evaluate_accuracy_guard


def _write_golden(tmp_path: Path, payload: dict, name: str = "golden.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_accuracy_guard_disabled_returns_none(tmp_path):
    summary = {"cycles": 100}
    outcome = evaluate_accuracy_guard(summary, {"enabled": False}, base_path=tmp_path)
    assert outcome is None


def test_accuracy_guard_passes_when_within_threshold(tmp_path):
    summary = {"cycles": 100, "miss_rates": {"l1": 0.1}}
    _write_golden(tmp_path, {"cycles": 100, "miss_rates": {"l1": 0.1}})

    outcome = evaluate_accuracy_guard(
        summary,
        {
            "enabled": True,
            "golds_path": "golden.json",
            "max_average_deviation": 0.2,
            "max_single_deviation": 0.2,
        },
        base_path=tmp_path,
    )

    assert outcome is not None
    assert outcome.passed is True
    assert outcome.payload["status"] == "ok"


def test_accuracy_guard_fails_when_deviation_exceeds_threshold(tmp_path):
    summary = {"cycles": 110}
    _write_golden(tmp_path, {"cycles": 100})

    outcome = evaluate_accuracy_guard(
        summary,
        {
            "enabled": True,
            "golds_path": "golden.json",
            "max_average_deviation": 0.05,
            "max_single_deviation": 0.05,
        },
        base_path=tmp_path,
    )

    assert outcome is not None
    assert outcome.passed is False
    assert outcome.payload["status"] == "failed"


def test_accuracy_guard_reports_missing_metrics(tmp_path):
    summary = {"cycles": 100}
    _write_golden(tmp_path, {"instructions_executed": 10})

    outcome = evaluate_accuracy_guard(
        summary,
        {
            "enabled": True,
            "golds_path": "golden.json",
            "max_average_deviation": 0.1,
            "max_single_deviation": 0.1,
        },
        base_path=tmp_path,
    )

    assert outcome is not None
    assert outcome.passed is False
    assert outcome.payload["status"] == "error"
    assert outcome.payload["missing_metrics"] == ["instructions_executed"]


def test_accuracy_guard_requires_golden_path(tmp_path):
    with pytest.raises(AccuracyGuardError):
        evaluate_accuracy_guard(
            {"cycles": 1},
            {"enabled": True, "golds_path": None},
            base_path=tmp_path,
        )
