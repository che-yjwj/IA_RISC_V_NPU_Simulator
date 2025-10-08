"""Export CQ dispatcher timelines to CSV for visualization."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _resolve_cq_summary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if "cq_execution" in payload:
        execution = payload["cq_execution"]
        if isinstance(execution, Mapping):
            return execution
    return payload


def _extract_timeline(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    dispatch = summary.get("dispatch")
    if not isinstance(dispatch, Mapping):
        raise ValueError("Summary does not contain a dispatch section.")
    timeline = dispatch.get("timeline")
    if timeline is None:
        raise ValueError(
            "Dispatch section does not include a timeline. "
            "Re-run the simulator with updated Stage 9 components."
        )
    if not isinstance(timeline, list):
        raise ValueError("Timeline field must be a list of entries.")
    records: list[Mapping[str, Any]] = []
    for entry in timeline:
        if not isinstance(entry, Mapping):
            raise ValueError("Timeline entries must be JSON objects.")
        required_fields = {"cmd_id", "start_tick", "end_tick", "lane"}
        missing = required_fields - set(entry)
        if missing:
            raise ValueError(
                f"Timeline entry missing required fields: {', '.join(sorted(missing))}"
            )
        records.append(entry)
    return records


def export_csv(entries: Sequence[Mapping[str, Any]], output: Path | None) -> None:
    headers = ("cmd_id", "start_tick", "end_tick", "lane")
    rows = [
        (
            str(entry["cmd_id"]),
            int(entry["start_tick"]),
            int(entry["end_tick"]),
            str(entry["lane"]),
        )
        for entry in entries
    ]

    if output is None:
        writer = csv.writer(_StdoutWrapper())
        writer.writerow(headers)
        writer.writerows(rows)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


class _StdoutWrapper:
    """Minimal wrapper to provide a file-like interface for csv.writer."""

    def __init__(self) -> None:
        import sys

        self._stream = sys.stdout

    def write(self, data: str) -> int:
        return self._stream.write(data)

    def flush(self) -> None:
        self._stream.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export CQ timeline data to CSV for plotting."
    )
    parser.add_argument(
        "summary",
        type=Path,
        help=(
            "Path to the CQ summary JSON (either direct simulator output or "
            "the full run-cq summary)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="CSV output path (default: stdout).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = json.loads(args.summary.read_text(encoding="utf-8"))
    summary = _resolve_cq_summary(payload)
    entries = _extract_timeline(summary)
    export_csv(entries, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
