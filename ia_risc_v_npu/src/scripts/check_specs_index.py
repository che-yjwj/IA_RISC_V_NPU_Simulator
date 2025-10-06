"""Verify that specs/README.md lists all specification files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Set

_ALLOWED_SUFFIXES = {".yaml", ".yml", ".md", ".json"}


def _gather_spec_files(spec_root: Path) -> Set[str]:
    files: Set[str] = set()
    for path in spec_root.iterdir():
        if not path.is_file():
            continue
        if path.name == "README.md":
            continue
        if path.suffix.lower() not in _ALLOWED_SUFFIXES:
            continue
        files.add(path.name)
    return files


def _extract_referenced_specs(readme: Path) -> Set[str]:
    pattern = re.compile(r"`([^`]+)`")
    entries: Set[str] = set()
    for line in readme.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        candidate = match.group(1).strip()
        if candidate and "/" not in candidate:
            entries.add(candidate)
    return entries


def _format_list(title: str, items: Iterable[str]) -> str:
    header = f"{title}:"
    body = "\n".join(f"  - {item}" for item in sorted(items))
    return f"{header}\n{body}" if items else header


def check_specs_index(repo_root: Path) -> int:
    spec_root = repo_root / "specs"
    readme = spec_root / "README.md"
    if not spec_root.is_dir():
        print(f"specs directory not found: {spec_root}", file=sys.stderr)
        return 1
    if not readme.is_file():
        print(f"specs/README.md not found at {readme}", file=sys.stderr)
        return 1

    actual = _gather_spec_files(spec_root)
    referenced = _extract_referenced_specs(readme)

    missing = actual - referenced
    extras = referenced - actual

    status = 0
    if missing:
        print(
            _format_list("Missing entries in specs/README.md", missing), file=sys.stderr
        )
        status = 1
    if extras:
        print(_format_list("README references missing files", extras), file=sys.stderr)
        status = 1

    if status == 0:
        print("specs/README.md covers all specification files.")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[3]
    return check_specs_index(repo_root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
