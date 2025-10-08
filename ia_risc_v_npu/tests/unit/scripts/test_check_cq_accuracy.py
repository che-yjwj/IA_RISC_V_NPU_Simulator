import json
from pathlib import Path
from typing import Dict

import pytest

from scripts import check_cq_accuracy


class DummyWorkload:
    def __init__(self, workload_id: str, trace: Path, config: Path, summary: Path):
        self.workload_id = workload_id
        self._trace = trace
        self._config = config
        self._summary = summary

    def trace_path(self, _: Path | None = None) -> Path:
        return self._trace

    def config_path(self, _: Path | None = None) -> Path:
        return self._config

    def accuracy_summary_path(self, _: Path | None = None) -> Path:
        return self._summary


@pytest.fixture()
def workload_paths(tmp_path: Path) -> Dict[str, Path]:
    trace = tmp_path / "trace.jsonl"
    trace.write_text("{}", encoding="utf-8")

    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"metric": 1}), encoding="utf-8")

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "accuracy_guard": {
                    "enabled": True,
                    "golds_path": str(summary),
                    "max_average_deviation": 0.05,
                    "max_single_deviation": 0.05,
                },
            }
        ),
        encoding="utf-8",
    )

    return {"trace": trace, "summary": summary, "config": config}


def test_run_collects_guard_results(workload_paths, monkeypatch, tmp_path):
    dummy = DummyWorkload(
        "dummy",
        workload_paths["trace"],
        workload_paths["config"],
        workload_paths["summary"],
    )

    def fake_iter():
        yield dummy

    def fake_compare(*_, **__):
        return {"cq_summary": {"metric": 1}}

    monkeypatch.setattr(check_cq_accuracy, "iter_workloads", fake_iter)
    monkeypatch.setattr(check_cq_accuracy, "GOLDEN_WORKLOADS", {"dummy": dummy})
    monkeypatch.setattr(check_cq_accuracy, "compare_cq_vs_elf", fake_compare)

    report = check_cq_accuracy.run()
    assert report["failed"] is False
    assert report["results"][0]["guard_passed"] is True
    assert report["results"][0]["status"] == "passed"


def test_main_writes_output_file(workload_paths, monkeypatch, tmp_path):
    dummy = DummyWorkload(
        "dummy",
        workload_paths["trace"],
        workload_paths["config"],
        workload_paths["summary"],
    )

    def fake_iter():
        yield dummy

    def fake_compare(*_, **__):
        return {"cq_summary": {"metric": 1}}

    monkeypatch.setattr(check_cq_accuracy, "iter_workloads", fake_iter)
    monkeypatch.setattr(check_cq_accuracy, "GOLDEN_WORKLOADS", {"dummy": dummy})
    monkeypatch.setattr(check_cq_accuracy, "compare_cq_vs_elf", fake_compare)

    output = tmp_path / "report.json"
    exit_code = check_cq_accuracy.main(["--output", str(output)])
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["failed"] is False
    assert data["results"][0]["workload_id"] == "dummy"
