import argparse
import json

import pytest

from src.simulator.cli import (
    CLIError,
    load_config,
    load_program_image,
    run_benchmark,
    run_simulate,
)
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
    def __init__(self, *, memsz: int, data: bytes = b"", paddr: int = 0, vaddr: int = 0, p_type: str = "PT_LOAD"):
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
    def __init__(self, text_section=None, sections=None, segments=None, entry_point: int = 0x100):
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


def test_load_program_image_requires_executable_section(tmp_path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    fake_elf = FakeELF(text_section=None, sections=[])

    monkeypatch.setattr("src.simulator.cli.ELFFile", lambda _: fake_elf)

    with pytest.raises(CLIError):
        load_program_image(elf_path)


def test_load_program_image_requires_load_segments(tmp_path, monkeypatch):
    elf_path = tmp_path / "program.elf"
    elf_path.write_bytes(b"ELF")
    words = [0x1]
    data = b"".join(word.to_bytes(4, "little") for word in words)
    fake_section = FakeSection(0x0, data)
    fake_elf = FakeELF(text_section=fake_section, segments=[])

    monkeypatch.setattr("src.simulator.cli.ELFFile", lambda _: fake_elf)

    with pytest.raises(CLIError):
        load_program_image(elf_path)


def test_run_simulate_writes_summary(tmp_path, monkeypatch):
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
    )

    exit_code = run_simulate(args)
    assert exit_code == 0

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["halted"] is True
    assert summary["reason"] == "halt"
    assert summary["instructions_executed"] == 1
    assert "bus_metrics" in summary


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
    assert "bus_metrics" in summary
