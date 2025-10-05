import json
import types

import pytest

from src.simulator import cli
from src.simulator.main import SimulationReport


class DummySimulator:
    def __init__(self) -> None:
        self.risc_v_engine = types.SimpleNamespace(instruction_count=0)

    def load_program(self, program) -> None:  # noqa: D401 - simple stub
        """Record the program without performing any work."""
        self.program = program


def _make_report(instructions: int) -> SimulationReport:
    return SimulationReport(
        cycles=instructions,
        instructions=instructions,
        halted=True,
        reason="halt",
        sim_time=instructions,
        elapsed_seconds=0.01,
        memory_report={},
        stall_breakdown={},
        npu_metrics={},
        fetch_metrics={},
    )


def _patch_benchmark(monkeypatch, metrics: cli.BenchmarkMetrics) -> None:
    def fake_measure(simulator, max_cycles):
        simulator.risc_v_engine.instruction_count = metrics.instructions_executed
        return _make_report(metrics.instructions_executed), metrics

    monkeypatch.setattr(
        cli, "AdaptiveSimulator", lambda *args, **kwargs: DummySimulator()
    )
    monkeypatch.setattr(cli, "_measure_performance", fake_measure)


def test_benchmark_mips_guard_passes(monkeypatch) -> None:
    metrics = cli.BenchmarkMetrics(
        elapsed_seconds=0.02, instructions_executed=16, mips=10.0
    )
    _patch_benchmark(monkeypatch, metrics)
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "benchmark",
            "--instructions",
            "8",
            "--min-mips",
            "8",
            "--max-mips",
            "12",
        ]
    )

    exit_code = args.handler(args)
    assert exit_code == 0


def test_benchmark_mips_guard_fails(monkeypatch, tmp_path) -> None:
    metrics = cli.BenchmarkMetrics(
        elapsed_seconds=0.02, instructions_executed=16, mips=6.5
    )
    _patch_benchmark(monkeypatch, metrics)
    parser = cli.build_parser()
    output_path = tmp_path / "summary.json"
    args = parser.parse_args(
        [
            "benchmark",
            "--instructions",
            "8",
            "--min-mips",
            "8",
            "--max-mips",
            "12",
            "--output",
            str(output_path),
        ]
    )

    exit_code = args.handler(args)
    assert exit_code == 1
    data = json.loads(output_path.read_text(encoding="utf-8"))
    guard = data.get("mips_guard")
    assert guard is not None
    assert guard["passed"] is False
    assert guard["measured_mips"] == pytest.approx(metrics.mips)
