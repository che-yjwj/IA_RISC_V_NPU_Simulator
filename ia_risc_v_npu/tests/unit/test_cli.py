import argparse
import json

import pytest

from src.simulator.cli import (
    CLIError,
    ProgramImage,
    load_config,
    load_program_image,
    run_benchmark,
    run_simulate,
)


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


class FakeELF:
    def __init__(self, text_section=None, sections=None):
        self._text_section = text_section
        self._sections = sections or []

    def get_section_by_name(self, name: str):
        if name == ".text":
            return self._text_section
        return None

    def iter_sections(self):
        return iter(self._sections)


def test_load_config_reads_json(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"max_cycles": 10}), encoding="utf-8")

    data = load_config(config_path)
    assert data == {"max_cycles": 10}


def test_load_program_image_uses_text_section(tmp_path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    words = [0xDEADBEEF, 0xCAFEBABE]
    data = b"".join(word.to_bytes(4, "little") for word in words)
    fake_section = FakeSection(0x100, data)
    fake_elf = FakeELF(text_section=fake_section)

    monkeypatch.setattr("src.simulator.cli.ELFFile", lambda _: fake_elf)

    image = load_program_image(elf_path)
    assert image.instructions == words
    assert image.text_size == len(data)


def test_load_program_image_requires_executable_section(tmp_path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    fake_elf = FakeELF(text_section=None, sections=[])

    monkeypatch.setattr("src.simulator.cli.ELFFile", lambda _: fake_elf)

    with pytest.raises(CLIError):
        load_program_image(elf_path)


def test_run_simulate_writes_summary(tmp_path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    output_path = tmp_path / "summary.json"

    program_image = ProgramImage(instructions=[0], text_size=4)
    monkeypatch.setattr("src.simulator.cli.load_program_image", lambda _: program_image)

    args = argparse.Namespace(
        elf_file=elf_path,
        config=None,
        output=output_path,
        verbose=False,
    )

    exit_code = run_simulate(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["halted"] is True
    assert summary["reason"] == "halt"
    assert summary["instructions_executed"] == 1


def test_run_benchmark_synthetic(tmp_path):
    output_path = tmp_path / "benchmark.json"

    args = argparse.Namespace(
        elf_file=None,
        instructions=1_000,
        max_cycles=0,
        config=None,
        output=output_path,
        verbose=False,
    )

    exit_code = run_benchmark(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["halted"] is True
    assert summary["instructions_executed"] >= args.instructions
    assert summary["mips"] > 0
    assert summary["elapsed_seconds"] > 0
