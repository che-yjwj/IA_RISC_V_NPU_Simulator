"""CLI to compare CQ and ELF execution summaries for benchmarking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from src.simulator.cq_runner import compare_cq_vs_elf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare CQ and ELF execution summaries"
    )
    parser.add_argument(
        "--cq", type=Path, required=True, help="Path to the CQ JSONL trace"
    )
    parser.add_argument(
        "--elf",
        type=Path,
        default=None,
        help="Optional ELF binary to run for comparison",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional simulator configuration JSON",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the raw comparison report as JSON",
    )
    parser.add_argument(
        "--show-dispatch",
        action="store_true",
        help=(
            "Include dispatcher metrics (queue wait, execution counts, DMA stats) "
            "in the human-readable output"
        ),
    )
    return parser


def _format_report(report: Dict[str, Any], *, verbose_dispatch: bool = False) -> str:
    lines = ["=== CQ vs ELF Comparison ==="]
    cq_summary = report["cq_summary"]
    elf_summary = report["elf_summary"]

    lines.append("CQ plan: {}".format(cq_summary["plan_summary"]))
    exec_counts = cq_summary.get("execution", {}).get("count", {})
    if exec_counts:
        lines.append("CQ execution counts: {}".format(exec_counts))

    if elf_summary.get("status") == "ok":
        metrics_line = (
            "ELF metrics: cycles={cycles} instructions={instructions} "
            "mips={mips:.2f}"
        ).format(**elf_summary)
        lines.append(metrics_line)
        cq_ops = len(cq_summary.get("execution", {}).get("executed", []))
        if cq_ops:
            ratio = elf_summary["instructions"] / cq_ops
            lines.append(f"Instructions per CQ command: {ratio:.2f}")
        cq_wait = cq_summary.get("dispatch", {}).get("queue_wait", {})
        if cq_wait:
            wait_avg = cq_wait.get("average")
            lines.append(f"CQ average queue wait: {wait_avg:.2f} cycles")
        cq_cycles = cq_summary.get("execution", {}).get("estimate_cycles")
        if cq_cycles:
            delta = elf_summary["cycles"] - cq_cycles
            lines.append(f"Cycle delta (ELF - CQ-estimate): {delta}")
    else:
        status = elf_summary.get("status")
        message = elf_summary.get("message", "n/a")
        lines.append(f"ELF status: {status} ({message})")

    if verbose_dispatch:
        lines.append("--- Dispatcher Metrics ---")
        dispatch = cq_summary.get("dispatch", {})
        execution = cq_summary.get("execution", {})
        lines.append(f"  executed: {dispatch.get('executed')}")
        lines.append(f"  rejected: {dispatch.get('rejected')}")
        lines.append(f"  queue_wait: {dispatch.get('queue_wait')}")
        lines.append(f"  execution.count: {execution.get('count')}")
        lines.append(f"  execution.dma_bytes: {execution.get('dma_bytes')}")
        lines.append(f"  execution.dma_cycles: {execution.get('dma_cycles')}")

    lines.append(f"Overall status: {report['status']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = compare_cq_vs_elf(
        cq_trace=args.cq,
        elf_path=args.elf,
        config_path=args.config,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_format_report(report, verbose_dispatch=args.show_dispatch))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
