"""Run vulture dead-code checks using project lint config."""

from __future__ import annotations

from ._runner import run_linter


def _flags(cfg: dict) -> list[str]:
    flags: list[str] = []
    if min_confidence := cfg.get("min_confidence"):
        flags += ["--min-confidence", str(min_confidence)]
    return flags + cfg.get("paths", ["linux_hi", "models", "tests"])


def main() -> None:
    """Run vulture with settings from config/lint.toml."""
    run_linter("vulture", _flags)


if __name__ == "__main__":
    main()
