import json
import logging
from argparse import Namespace
from pathlib import Path

from src.cq.tools import plan_generator
from src.simulator.cli import run_cq


def test_run_cq_writes_summary(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    yaml_path = root / "workloads" / "cq" / "sample_gemm.yaml"
    trace_path = tmp_path / "sample_gemm.jsonl"
    plan_generator.run(
        plan_generator.build_parser().parse_args(
            ["--input", str(yaml_path), "--output", str(trace_path)]
        )
    )
    output_path = tmp_path / "summary.json"

    monkeypatch.setattr(
        "src.simulator.cli.configure_logging",
        lambda *args, **kwargs: logging.getLogger("simulator"),
    )

    args = Namespace(
        trace_path=trace_path,
        trace=[],
        config=None,
        output=output_path,
        allow_forward_deps=False,
        isa_spec=None,
        skip_isa_check=False,
        verbose=False,
        log_level=None,
        log_path=None,
        scheduler_policy=None,
    )

    exit_code = run_cq(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["status"] == "validated"
    assert summary["command_count"] == 3
    assert summary["opcode_histogram"] == {"DMA_2D": 2, "TE_GEMM": 1}
    assert summary["metadata"]["name"] == "sample_gemm"
    assert summary["dependency_stats"]["roots"] == 1


def test_cli_main_handles_trace_argument(tmp_path: Path):
    from src.simulator.cli import main

    root = Path(__file__).resolve().parents[3]
    yaml_path = root / "workloads" / "cq" / "sample_gemm.yaml"
    trace_path = tmp_path / "sample_gemm.jsonl"
    plan_generator.run(
        plan_generator.build_parser().parse_args(
            ["--input", str(yaml_path), "--output", str(trace_path)]
        )
    )
    output_path = tmp_path / "summary.json"

    exit_code = main(["run-cq", str(trace_path), "--output", str(output_path)])
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["status"] == "validated"
