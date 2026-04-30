"""Run lizard complexity checks using project lint config."""

from __future__ import annotations

from ._runner import run_linter


def _flags(cfg: dict) -> list[str]:
    flags: list[str] = []
    if ccn := cfg.get("ccn"):
        flags += ["--CCN", str(ccn)]
    if length := cfg.get("length"):
        flags += ["--length", str(length)]
    if cfg.get("warnings_only"):
        flags += ["--warnings_only"]
    return flags + cfg.get("paths", ["linux_hi", "models"])


def main() -> None:
    """Run lizard with settings from config/lint.toml."""
    run_linter("lizard", _flags)


if __name__ == "__main__":
    main()
