"""Run vulture dead-code checks using project lint config."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from linux_hi.process.exec import run_resolved

_CONFIG = Path("config/lint.toml")


def main() -> None:
    """Run vulture with settings from config/lint.toml."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8")).get("vulture", {})
    cmd = ["vulture"]
    if min_confidence := cfg.get("min_confidence"):
        cmd += ["--min-confidence", str(min_confidence)]
    cmd += cfg.get("paths", ["linux_hi", "models", "tests"])
    sys.exit(run_resolved(cmd).returncode)


if __name__ == "__main__":
    main()
