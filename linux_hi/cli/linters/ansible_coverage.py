"""Check that each ansible app has a corresponding test file in tests/apps/."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

_CONFIG = Path("config/lint.toml")
_APPS_DIR = Path("ansible/apps")
_TESTS_DIR = Path("tests/apps")


def _expected_test_file(app_name: str) -> Path:
    """Return the expected test file path for *app_name*."""
    sanitised = app_name.replace("-", "_")
    return _TESTS_DIR / f"test_{sanitised}.py"


def main() -> None:
    """Report ansible app test coverage and exit non-zero if below the floor."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    floor: int = cfg.get("ansible_coverage", {}).get("floor", 0)

    apps = sorted(p.name for p in _APPS_DIR.iterdir() if p.is_dir())
    covered = [a for a in apps if _expected_test_file(a).exists()]
    missing = [a for a in apps if a not in covered]

    total = len(apps)
    pct = int(100 * len(covered) / total) if total else 100

    print(f"Ansible app test coverage: {len(covered)}/{total} ({pct}%)")
    if covered:
        for a in covered:
            print(f"  [ok]      {a}")
    if missing:
        for a in missing:
            print(f"  [missing] {a}  → {_expected_test_file(a)}")

    if pct < floor:
        print(f"\nFAIL: coverage {pct}% is below the floor of {floor}%")
        sys.exit(1)

    if missing:
        print(f"\nWARNING: {len(missing)} app(s) have no test file (coverage meets floor {floor}%)")

    sys.exit(0)


if __name__ == "__main__":
    main()
