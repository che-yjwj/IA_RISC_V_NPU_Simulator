import json
from pathlib import Path

import pytest

from src.cq import (
    CommandQueue,
    CQCommand,
    CQValidationError,
    dump_cq_trace,
    load_cq_trace,
)
from src.cq.io import CQIOError


def build_queue() -> CommandQueue:
    commands = [
        {
            "cmd_id": "cmd0",
            "opcode": "DMA_2D",
            "operands": {"size": 1024, "stride": [64, 64]},
        },
        {
            "cmd_id": "cmd1",
            "opcode": "TE_GEMM",
            "deps": ["cmd0"],
            "operands": {"m": 64, "n": 64, "k": 64},
            "priority": 1,
        },
    ]
    metadata = {"workload": "unit-test", "version": 1}
    return CommandQueue.from_iterable(commands, metadata=metadata)


def test_dump_and_load_roundtrip(tmp_path: Path) -> None:
    queue = build_queue()
    path = tmp_path / "trace.jsonl"
    dump_cq_trace(queue, path)

    loaded = load_cq_trace(path)

    assert loaded.metadata == queue.metadata
    assert loaded.command_ids() == queue.command_ids()
    assert loaded.commands[1].attributes["priority"] == 1
    assert loaded.commands[1].operands["m"] == 64


def test_load_with_missing_dependency_raises(tmp_path: Path) -> None:
    path = tmp_path / "invalid.jsonl"
    payload = {"cmd_id": "cmd1", "opcode": "TE_GEMM", "deps": ["cmd0"]}
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(CQIOError):
        load_cq_trace(path)


def test_allow_forward_dependencies(tmp_path: Path) -> None:
    path = tmp_path / "forward.jsonl"
    entries = [
        {"cmd_id": "cmd1", "opcode": "TE_GEMM", "deps": ["cmd2"]},
        {"cmd_id": "cmd2", "opcode": "DMA_2D"},
    ]
    path.write_text(
        "\n".join(json.dumps(item) for item in entries) + "\n", encoding="utf-8"
    )

    queue = load_cq_trace(path, strict=False)

    assert queue.command_ids() == ("cmd1", "cmd2")


def test_duplicate_command_id_rejected() -> None:
    commands = [
        {"cmd_id": "cmd0", "opcode": "DMA_2D"},
        {"cmd_id": "cmd0", "opcode": "DMA_2D"},
    ]

    with pytest.raises(CQValidationError):
        CommandQueue.from_iterable(commands)


def test_duplicate_dependencies_rejected() -> None:
    command = {"cmd_id": "cmd0", "opcode": "DMA_2D", "deps": ["cmd1", "cmd1"]}

    with pytest.raises(CQValidationError):
        CQCommand.from_dict(command)
