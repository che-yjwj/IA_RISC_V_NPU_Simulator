import json
import logging
from argparse import Namespace
from pathlib import Path

from src.simulator.cli import _generate_synthetic_program, run_simulate


def test_run_simulate_executes_synthetic_program(tmp_path, monkeypatch):
    output_path = tmp_path / "summary.json"
    elf_path = tmp_path / "dummy.elf"

    # Stub logger setup to avoid mutating global logging state during the test run.
    monkeypatch.setattr(
        "src.simulator.cli.configure_logging",
        lambda *args, **kwargs: logging.getLogger("simulator-test"),
    )

    def fake_load_program_image(path: Path):
        # Ensure the CLI still passes through the ELF file path.
        assert path == elf_path
        return _generate_synthetic_program(length=4)

    monkeypatch.setattr("src.simulator.cli.load_program_image", fake_load_program_image)

    args = Namespace(
        elf_file=elf_path,
        config=None,
        output=output_path,
        verbose=False,
        log_level=None,
        log_path=None,
        trace=[],
        scheduler_policy=None,
    )

    exit_code = run_simulate(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["instructions_executed"] > 0
    assert summary["cycles"] >= summary["instructions_executed"]
