"""Shared runner for config-driven lint tools."""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

from linux_hi.utils.exec import run_resolved

_CONFIG = Path("config/lint.toml")


def run_linter(name: str, build_flags: Callable[[dict], list[str]]) -> None:
    """Load *name* section from lint config, build cmd, run, and exit."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8")).get(name, {})
    sys.exit(run_resolved([name] + build_flags(cfg)).returncode)
