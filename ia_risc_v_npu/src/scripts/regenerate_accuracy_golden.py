"""Utility to regenerate the accuracy guard golden summary for demo workloads."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG = Path(
    "ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json"
)
DEFAULT_GOLDEN = Path(
    "ia_risc_v_npu/workloads/demos/accuracy_guard/configs/golden_summary.json"
)


def _run_benchmark(config: Path, instructions: int, output_path: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "src.simulator.cli",
        "benchmark",
        "--instructions",
        str(instructions),
        "--config",
        str(config),
        "--output",
        str(output_path),
    ]
    subprocess.run(command, check=True)


def _load_summary(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_golden(summary: Dict[str, Any]) -> Dict[str, Any]:
    def pick(container: Dict[str, Any], key: str, default: Any = 0) -> Any:
        return container.get(key, default)

    memory_report = summary.get("memory_report", {})
    bus = memory_report.get("bus", {})
    memory_system = memory_report.get("memory_system", {})
    npu_metrics = summary.get("npu_metrics", {})
    fetch_metrics = summary.get("fetch_metrics", {})
    cpu_metrics = summary.get("cpu_metrics", {})
    wait_metrics = summary.get("wait_metrics", {})

    return {
        "cycles": pick(summary, "cycles"),
        "instructions_executed": pick(summary, "instructions_executed"),
        "sim_time": pick(summary, "sim_time"),
        "miss_rates": summary.get("miss_rates", {}),
        "memory_report": {
            "bus": {
                "completed_requests": pick(bus, "completed_requests"),
                "avg_wait_cycles": pick(bus, "avg_wait_cycles"),
                "total_wait_cycles": pick(bus, "total_wait_cycles"),
            },
            "memory_system": {
                "total_requests": pick(memory_system, "total_requests"),
                "average_latency_cycles": pick(memory_system, "average_latency_cycles"),
                "dram_wait_cycles": pick(memory_system, "dram_wait_cycles"),
            },
        },
        "npu_metrics": {
            "cores": pick(npu_metrics, "cores"),
            "tasks": pick(npu_metrics, "tasks"),
            "utilization": pick(npu_metrics, "utilization"),
            "wait_cycles": pick(npu_metrics, "wait_cycles"),
            "avg_wait_cycles": pick(npu_metrics, "avg_wait_cycles"),
        },
        "fetch_metrics": {
            "fetches": pick(fetch_metrics, "fetches"),
            "hit_rate": pick(fetch_metrics, "hit_rate"),
            "miss_rate": pick(fetch_metrics, "miss_rate"),
            "latency_p90": pick(fetch_metrics, "latency_p90"),
            "latency_p99": pick(fetch_metrics, "latency_p99"),
        },
        "cpu_metrics": {
            "active_cycles": pick(cpu_metrics, "active_cycles"),
            "stall_cycles": pick(cpu_metrics, "stall_cycles"),
            "utilization": pick(cpu_metrics, "utilization"),
        },
        "wait_metrics": {
            "cpu_total_wait_cycles": pick(wait_metrics, "cpu_total_wait_cycles"),
            "bus_total_wait_cycles": pick(wait_metrics, "bus_total_wait_cycles"),
            "bus_avg_wait_cycles": pick(wait_metrics, "bus_avg_wait_cycles"),
            "dram_wait_cycles": pick(wait_metrics, "dram_wait_cycles"),
            "npu_wait_cycles": pick(wait_metrics, "npu_wait_cycles"),
            "npu_avg_wait_cycles": pick(wait_metrics, "npu_avg_wait_cycles"),
            "npu_avg_turnaround_cycles": pick(
                wait_metrics, "npu_avg_turnaround_cycles"
            ),
        },
    }


def regenerate(config: Path, golden_path: Path, instructions: int) -> None:
    config = config.resolve()
    golden_path = golden_path.resolve()

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        temp_path = Path(tmp.name)

    try:
        _run_benchmark(config, instructions, temp_path)
        summary = _load_summary(temp_path)

        guard = summary.get("accuracy_guard", {})
        if guard.get("status") != "ok":
            raise RuntimeError(
                "Accuracy guard reported a failure; aborting golden regeneration"
            )

        golden_payload = _build_golden(summary)
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        with golden_path.open("w", encoding="utf-8") as handle:
            json.dump(golden_payload, handle, indent=2, ensure_ascii=False)
    finally:
        temp_path.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate the accuracy guard golden summary"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Simulator config JSON used during regeneration",
    )
    parser.add_argument(
        "--golds",
        type=Path,
        default=DEFAULT_GOLDEN,
        help="Target golden JSON path to overwrite",
    )
    parser.add_argument(
        "--instructions",
        type=int,
        default=1,
        help="Instruction budget passed to the benchmark runner",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    regenerate(args.config, args.golds, args.instructions)
    print(f"Updated golden summary at {args.golds}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
