"""Check CQ golden workloads against accuracy guard references."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from src.simulator.accuracy import (
    AccuracyGuardOutcome,
    evaluate_accuracy_guard,
)
from src.simulator.cq_runner import compare_cq_vs_elf
from workloads.golden import GOLDEN_WORKLOADS, GoldenWorkload, iter_workloads


@dataclass(slots=True)
class WorkloadResult:
    workload_id: str
    status: str
    guard_passed: bool | None
    summary_path: Path
    guard_payload: Mapping[str, Any] | None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "workload_id": self.workload_id,
            "status": self.status,
            "summary_path": str(self.summary_path),
        }
        if self.guard_passed is not None:
            payload["guard_passed"] = self.guard_passed
        if self.guard_payload is not None:
            payload["accuracy_guard"] = self.guard_payload
        return payload


def _load_config(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file is not valid JSON: {path}") from exc


def _resolve_workloads(selected: Sequence[str] | None) -> Iterable[GoldenWorkload]:
    if not selected:
        yield from iter_workloads()
        return

    unknown = [
        workload_id for workload_id in selected if workload_id not in GOLDEN_WORKLOADS
    ]
    if unknown:
        ids = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown workload id(s): {ids}")

    for workload_id in selected:
        yield GOLDEN_WORKLOADS[workload_id]


def _run_guard(
    summary: Mapping[str, Any],
    accuracy_guard_config: Mapping[str, Any],
    *,
    base_path: Path,
) -> AccuracyGuardOutcome | None:
    return evaluate_accuracy_guard(
        dict(summary),
        dict(accuracy_guard_config),
        base_path=base_path,
    )


def _resolve_path(
    resolver: Any,
    base_dir: Path | None,
) -> Path | None:
    if base_dir is None:
        return resolver()
    return resolver(base_dir)


def evaluate_workload(
    workload: GoldenWorkload,
    *,
    base_dir: Path | None = None,
) -> WorkloadResult:
    trace_path = _resolve_path(workload.trace_path, base_dir)
    config_path = _resolve_path(workload.config_path, base_dir)
    summary_path = _resolve_path(workload.accuracy_summary_path, base_dir)
    if summary_path is None:
        raise ValueError(
            f"No summary path registered for workload {workload.workload_id}"
        )

    config = _load_config(config_path)
    guard_config = config.get("accuracy_guard", {})
    result = compare_cq_vs_elf(cq_trace=trace_path, config_path=config_path)
    cq_summary = result.get("cq_summary", {})

    guard_outcome = None
    if guard_config.get("enabled", False):
        guard_outcome = _run_guard(
            cq_summary,
            guard_config,
            base_path=config_path.parent,
        )

    if guard_config.get("enabled", False) and guard_outcome is None:
        status = "guard_skipped"
        guard_passed = None
    elif guard_outcome is None:
        status = "guard_disabled"
        guard_passed = None
    else:
        status = "passed" if guard_outcome.passed else "failed"
        guard_passed = guard_outcome.passed

    return WorkloadResult(
        workload_id=workload.workload_id,
        status=status,
        guard_passed=guard_passed,
        summary_path=summary_path,
        guard_payload=guard_outcome.payload if guard_outcome is not None else None,
    )


def run(
    *,
    workload_ids: Sequence[str] | None = None,
    fail_fast: bool = False,
    base_dir: Path | None = None,
) -> Dict[str, Any]:
    failures: List[Mapping[str, Any]] = []
    results: List[Mapping[str, Any]] = []
    for workload in _resolve_workloads(workload_ids):
        outcome = evaluate_workload(workload, base_dir=base_dir)
        payload = outcome.to_dict()
        results.append(payload)
        if outcome.guard_passed is False:
            failures.append(payload)
            if fail_fast:
                break

    report = {
        "results": results,
        "failures": failures,
        "failed": bool(failures),
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate CQ golden workloads against accuracy guard references",
    )
    parser.add_argument(
        "--workload",
        action="append",
        dest="workload_ids",
        help="Run the accuracy check for a specific workload id (repeatable)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop evaluation after the first failed workload",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the JSON report to the specified file (prints to stdout otherwise)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run(
            workload_ids=args.workload_ids,
            fail_fast=args.fail_fast,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    else:
        print(json.dumps(report, indent=2))

    return 1 if report["failed"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
