import argparse
import json
from pathlib import Path

import pytest

from src.simulator.cli import (
    TRACE_COMPONENT_CHOICES,
    CLIError,
    configure_logging,
    load_config,
    load_program_image,
    run_benchmark,
    run_simulate,
)
from src.simulator.config import default_simulator_config
from src.simulator.program import ProgramImage, ProgramSegment


class FakeSection:
    def __init__(self, addr: int, data: bytes, flags: int = 0x4):
        self._addr = addr
        self._data = data
        self._flags = flags

    def data(self) -> bytes:
        return self._data

    def __getitem__(self, key: str):
        if key == "sh_addr":
            return self._addr
        if key == "sh_flags":
            return self._flags
        raise KeyError(key)


class FakeSegment:
    def __init__(
        self,
        *,
        memsz: int,
        data: bytes = b"",
        paddr: int = 0,
        vaddr: int = 0,
        p_type: str = "PT_LOAD",
    ):
        self._memsz = memsz
        self._data = data
        self._paddr = paddr
        self._vaddr = vaddr
        self._type = p_type

    def data(self) -> bytes:
        return self._data

    def __getitem__(self, key: str):
        if key == "p_memsz":
            return self._memsz
        if key == "p_paddr":
            return self._paddr
        if key == "p_vaddr":
            return self._vaddr
        if key == "p_type":
            return self._type
        raise KeyError(key)


class FakeELF:
    def __init__(
        self, text_section=None, sections=None, segments=None, entry_point: int = 0x100
    ):
        self._text_section = text_section
        self._sections = sections or []
        self._segments = segments or []
        self.header = {"e_entry": entry_point}

    def get_section_by_name(self, name: str):
        if name == ".text":
            return self._text_section
        return None

    def iter_sections(self):
        return iter(self._sections)

    def iter_segments(self):
        return iter(self._segments)


def test_load_config_reads_json(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "max_cycles": 10,
                "cpu": {"execution": {"mul_latency": 5}},
            }
        ),
        encoding="utf-8",
    )

    data = load_config(config_path)
    assert data["schema_version"] == 1
    assert data["max_cycles"] == 10
    assert data["cpu"]["execution"]["mul_latency"] == 5
    # Defaults remain intact for unspecified keys
    assert data["cpu"]["execution"]["div_latency"] == 10
    assert data["cache"]["l1"]["size_bytes"] == 32 * 1024


def test_load_program_image_uses_text_section(tmp_path: Path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    words = [0xDEADBEEF, 0xCAFEBABE]
    data = b"".join(word.to_bytes(4, "little") for word in words)
    fake_section = FakeSection(0x100, data)
    fake_segment = FakeSegment(memsz=len(data), data=data, paddr=0x100, vaddr=0x100)
    fake_elf = FakeELF(text_section=fake_section, segments=[fake_segment])

    monkeypatch.setattr("src.simulator.cli.ELFFile", lambda _: fake_elf)

    image = load_program_image(elf_path)
    assert image.instructions == words
    assert image.text_size == len(data)
    assert image.entry_point == 0x100
    assert len(image.segments) == 1
    segment = image.segments[0]
    assert segment.address == 0x100
    assert segment.mem_size == len(data)
    assert segment.data == data


def test_load_program_image_requires_executable_section(tmp_path: Path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    fake_elf = FakeELF(text_section=None, sections=[])

    monkeypatch.setattr("src.simulator.cli.ELFFile", lambda _: fake_elf)

    with pytest.raises(CLIError):
        load_program_image(elf_path)


def test_load_program_image_requires_load_segments(tmp_path: Path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    words = [0x1]
    data = b"".join(word.to_bytes(4, "little") for word in words)
    fake_section = FakeSection(0x0, data)
    fake_elf = FakeELF(text_section=fake_section, segments=[])

    monkeypatch.setattr("src.simulator.cli.ELFFile", lambda _: fake_elf)

    with pytest.raises(CLIError):
        load_program_image(elf_path)


def test_load_config_invalid_schema(tmp_path: Path):
    config_path = tmp_path / "invalid.json"
    config_path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")

    with pytest.raises(CLIError):
        load_config(config_path)


def test_run_simulate_writes_summary(tmp_path: Path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    output_path = tmp_path / "summary.json"

    segment = ProgramSegment(address=0, data=(0).to_bytes(4, "little"), mem_size=4)
    program_image = ProgramImage(
        instructions=[0],
        text_size=4,
        entry_point=0,
        segments=[segment],
    )
    monkeypatch.setattr("src.simulator.cli.load_program_image", lambda _: program_image)

    args = argparse.Namespace(
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
    assert summary["halted"] is True
    assert summary["reason"] == "halt"
    assert summary["instructions_executed"] == 1
    assert "memory_report" in summary
    assert "miss_rates" in summary
    assert "l1" in summary["miss_rates"]
    assert "amat_cycles" in summary
    assert "stall_breakdown" in summary
    assert "npu_util" in summary
    assert "accuracy_guard" not in summary


def test_run_benchmark_synthetic(tmp_path: Path):
    output_path = tmp_path / "benchmark.json"

    args = argparse.Namespace(
        elf_file=None,
        instructions=1_000,
        max_cycles=0,
        min_mips=None,
        max_mips=None,
        config=None,
        output=output_path,
        verbose=False,
        log_level=None,
        log_path=None,
        trace=[],
        scheduler_policy=None,
    )

    exit_code = run_benchmark(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["halted"] is True
    assert summary["instructions_executed"] >= args.instructions
    assert summary["mips"] > 0
    assert summary["elapsed_seconds"] > 0
    assert "memory_report" in summary
    assert "miss_rates" in summary
    assert "amat_cycles" in summary
    assert "npu_util" in summary


def test_configure_logging_trace_overrides_parent_level():
    import logging

    root = logging.getLogger()
    original_root_level = root.level
    handler_levels = [handler.level for handler in root.handlers]

    simulator_logger = logging.getLogger("simulator")
    original_sim_level = simulator_logger.level
    component_levels = {
        name: logging.getLogger(f"simulator.{name}").level
        for name in TRACE_COMPONENT_CHOICES
    }
    module_logger = logging.getLogger("src.simulator.cli")
    original_module_level = module_logger.level

    try:
        config = default_simulator_config()
        config["logging"]["level"] = "INFO"
        configure_logging(
            config, verbose=False, log_level=None, trace_components=["bus"]
        )

        assert logging.getLogger("simulator").level == logging.DEBUG
        assert logging.getLogger("simulator.bus").level == logging.DEBUG
        assert logging.getLogger("simulator.memory").level == logging.INFO
        assert logging.getLogger("simulator.npu").level == logging.INFO
    finally:
        root.setLevel(original_root_level)
        for handler, level in zip(root.handlers, handler_levels):
            handler.setLevel(level)

        simulator_logger.setLevel(original_sim_level)
        for name, level in component_levels.items():
            logging.getLogger(f"simulator.{name}").setLevel(level)

        module_logger.setLevel(original_module_level)


def test_run_simulate_applies_scheduler_override(tmp_path: Path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    output_path = tmp_path / "summary.json"

    program_image = _make_program_image()
    monkeypatch.setattr("src.simulator.cli.load_program_image", lambda _: program_image)

    captured: dict[str, object] = {}

    class DummySimulator:
        def __init__(self, *, config, logger):
            captured["config"] = config
            self.logger = logger
            self.risc_v_engine = argparse.Namespace(instruction_count=1)

        def load_program(self, program):  # pragma: no cover - simple passthrough
            captured["program"] = program

        async def run_simulation(self, max_cycles: int = 0):
            from src.simulator.main import SimulationReport

            return SimulationReport(
                cycles=1,
                instructions=1,
                halted=True,
                reason="halt",
                sim_time=1,
                elapsed_seconds=0.001,
                memory_report={
                    "caches": {},
                    "memory_system": {
                        "average_latency_cycles": 0.0,
                        "dram_wait_cycles": 0.0,
                    },
                    "bus": {
                        "total_wait_cycles": 0.0,
                        "avg_wait_cycles": 0.0,
                    },
                },
                stall_breakdown={},
                npu_metrics={
                    "utilization": 0.0,
                    "wait_cycles": 0.0,
                    "avg_wait_cycles": 0.0,
                    "avg_turnaround_cycles": 0.0,
                },
                fetch_metrics={},
            )

    monkeypatch.setattr("src.simulator.cli.AdaptiveSimulator", DummySimulator)

    args = argparse.Namespace(
        elf_file=elf_path,
        config=None,
        output=output_path,
        verbose=False,
        log_level=None,
        log_path=None,
        trace=[],
        scheduler_policy="rr",
    )

    exit_code = run_simulate(args)

    assert exit_code == 0
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["halted"] is True
    assert summary["reason"] == "halt"
    assert captured["config"]["npu"]["policy"] == "rr"


def _make_program_image() -> ProgramImage:
    segment = ProgramSegment(address=0, data=(0).to_bytes(4, "little"), mem_size=4)
    return ProgramImage(
        instructions=[0],
        text_size=4,
        entry_point=0,
        segments=[segment],
    )


def test_run_simulate_with_accuracy_guard_pass(tmp_path: Path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    output_path = tmp_path / "summary.json"
    golden_path = tmp_path / "golden.json"

    program_image = _make_program_image()
    monkeypatch.setattr("src.simulator.cli.load_program_image", lambda _: program_image)

    # Expected metrics aligned with the simulated program
    golden_path.write_text(
        json.dumps({"cycles": 1, "instructions_executed": 1}),
        encoding="utf-8",
    )

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "accuracy_guard": {
                    "enabled": True,
                    "golds_path": golden_path.name,
                    "max_average_deviation": 0.2,
                    "max_single_deviation": 0.2,
                }
            }
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        elf_file=elf_path,
        config=config_path,
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
    assert summary["accuracy_guard"]["status"] == "ok"
    assert summary["accuracy_guard"]["golds_path"].endswith(golden_path.name)


def test_run_simulate_with_accuracy_guard_failure(tmp_path: Path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    output_path = tmp_path / "summary.json"
    golden_path = tmp_path / "golden.json"

    program_image = _make_program_image()
    monkeypatch.setattr("src.simulator.cli.load_program_image", lambda _: program_image)

    golden_path.write_text(json.dumps({"cycles": 9999}), encoding="utf-8")

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "accuracy_guard": {
                    "enabled": True,
                    "golds_path": golden_path.name,
                    "max_average_deviation": 0.01,
                    "max_single_deviation": 0.01,
                }
            }
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        elf_file=elf_path,
        config=config_path,
        output=output_path,
        verbose=False,
        log_level=None,
        log_path=None,
        trace=[],
        scheduler_policy=None,
    )

    exit_code = run_simulate(args)
    assert exit_code == 1

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["accuracy_guard"]["status"] == "failed"
