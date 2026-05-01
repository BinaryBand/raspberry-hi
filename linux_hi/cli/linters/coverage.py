"""Run pytest coverage check using project lint config."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from linux_hi.utils.exec import run_resolved

_CONFIG = Path("config/lint.toml")


def main() -> None:
    """Run pytest --cov with the floor defined in config/lint.toml."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    floor = cfg["coverage"]["floor"]
    result = run_resolved(
        [
            "poetry",
            "run",
            "pytest",
            "-q",
            "tests/",
            "--ignore=tests/unit/test_lint.py",
            "--cov=linux_hi",
            "--cov-report=term",
            f"--cov-fail-under={floor}",
        ]
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
