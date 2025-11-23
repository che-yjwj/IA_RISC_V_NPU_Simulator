"""Test configuration for shared path setup."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATHS = [PROJECT_ROOT / "src", PROJECT_ROOT]

for path in PATHS:
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)
