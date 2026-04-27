"""Run lizard complexity checks using project lint config."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from linux_hi.process.exec import run_resolved

_CONFIG = Path("config/lint.toml")


def main() -> None:
    """Run lizard with settings from config/lint.toml."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8")).get("lizard", {})
    cmd = ["lizard"]
    if ccn := cfg.get("ccn"):
        cmd += ["--CCN", str(ccn)]
    if length := cfg.get("length"):
        cmd += ["--length", str(length)]
    if cfg.get("warnings_only"):
        cmd += ["--warnings_only"]
    cmd += cfg.get("paths", ["linux_hi", "models"])
    sys.exit(run_resolved(cmd).returncode)


if __name__ == "__main__":
    main()
