"""IO helpers for reading and writing CQ traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, MutableMapping, Optional, TextIO

from .schema import CommandQueue, CQValidationError


class CQIOError(RuntimeError):
    """Raised when a CQ trace cannot be read or written."""


def _normalise_path(path: str | Path) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def load_cq_trace(
    path: str | Path,
    *,
    strict: bool = True,
) -> CommandQueue:
    """Load a JSONL-formatted CQ trace from *path*.

    Each non-empty line must contain a JSON object.  Lines of the form
    ``{"metadata": {...}}`` append to the top-level metadata dictionary and are
    ignored for the command stream.  All other objects are treated as command
    payloads.
    """

    resolved = _normalise_path(path)
    metadata: MutableMapping[str, object] = {}
    commands: list[Mapping[str, object]] = []
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            for index, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:  # pragma: no cover - syntax guard
                    raise CQIOError(
                        f"Failed to parse JSON on line {index} of {resolved}: {exc}"
                    ) from exc

                if not isinstance(payload, Mapping):
                    raise CQIOError(
                        f"Line {index} of {resolved} must contain a JSON object"
                    )

                if set(payload.keys()) == {"metadata"}:
                    meta = payload["metadata"]
                    if meta is None:
                        continue
                    if not isinstance(meta, Mapping):
                        raise CQIOError(
                            f"metadata entry on line {index} must be an object"
                        )
                    metadata.update(meta)
                    continue

                commands.append(payload)
    except OSError as exc:  # pragma: no cover - filesystem failure
        raise CQIOError(f"Failed to read CQ trace: {resolved}") from exc

    try:
        return CommandQueue.from_iterable(commands, metadata=metadata, strict=strict)
    except CQValidationError as exc:
        raise CQIOError(f"Invalid CQ trace {resolved}: {exc}") from exc


def dump_cq_trace(
    trace: CommandQueue,
    path: str | Path,
    *,
    metadata: Optional[Mapping[str, object]] = None,
) -> None:
    """Persist *trace* to *path* in JSONL format."""

    resolved = _normalise_path(path)
    meta = metadata if metadata is not None else trace.metadata
    try:
        with resolved.open("w", encoding="utf-8") as handle:
            _write_trace(handle, trace, metadata=meta)
    except OSError as exc:  # pragma: no cover - filesystem failure
        raise CQIOError(f"Failed to write CQ trace: {resolved}") from exc


def _write_trace(
    handle: TextIO,
    trace: CommandQueue,
    *,
    metadata: Optional[Mapping[str, object]] = None,
) -> None:
    if metadata:
        json.dump({"metadata": dict(metadata)}, handle, ensure_ascii=False)
        handle.write("\n")
    for command in trace:
        json.dump(command.to_dict(), handle, ensure_ascii=False)
        handle.write("\n")


__all__ = ["CQIOError", "load_cq_trace", "dump_cq_trace"]
