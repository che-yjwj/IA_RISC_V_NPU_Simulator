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
        cq_policy=None,
        cq_lane_limit=None,
        simulate=False,
    )

    exit_code = run_cq(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["status"] == "validated"


def test_run_cq_simulate_includes_execution(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    yaml_path = root / "workloads" / "cq" / "sample_gemm.yaml"
    trace_path = tmp_path / "sample_gemm.jsonl"
    plan_generator.run(
        plan_generator.build_parser().parse_args(
            ["--input", str(yaml_path), "--output", str(trace_path)]
        )
    )
    output_path = tmp_path / "simulate_summary.json"

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
        cq_policy=None,
        cq_lane_limit=None,
        simulate=True,
    )

    exit_code = run_cq(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["status"] == "simulated"
    cq_execution = summary["cq_execution"]
    assert cq_execution["status"] == "cq_actions_executed"
    lane_usage = cq_execution["dispatch"]["lane_usage"]
    assert lane_usage["totals"]["dma"] == 2
    assert lane_usage["totals"]["te"] == 1
    assert lane_usage["max_concurrency"]["dma"] >= 1
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


def test_run_cq_simulate_conv_workload(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    yaml_path = root / "workloads" / "cq" / "sample_conv.yaml"
    trace_path = tmp_path / "sample_conv.jsonl"
    plan_generator.run(
        plan_generator.build_parser().parse_args(
            ["--input", str(yaml_path), "--output", str(trace_path)]
        )
    )
    output_path = tmp_path / "conv_summary.json"

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
        cq_policy=None,
        cq_lane_limit=None,
        simulate=True,
    )

    exit_code = run_cq(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["status"] == "simulated"
    assert summary["metadata"]["name"] == "sample_conv"
    histogram = summary["opcode_histogram"]
    assert histogram["DMA_2D"] == 3
    assert histogram["TE_GEMM"] == 1
    assert histogram["FENCE_SPM"] == 1
    cq_execution = summary["cq_execution"]
    assert cq_execution["status"] == "cq_actions_executed"
    lane_usage = cq_execution["dispatch"]["lane_usage"]
    assert lane_usage["totals"]["dma"] == 3
    assert lane_usage["totals"]["te"] == 1
    assert lane_usage["totals"]["fence"] == 1
    timeline = cq_execution["dispatch"]["timeline"]
    assert any(entry["lane"] == "te" for entry in timeline)
