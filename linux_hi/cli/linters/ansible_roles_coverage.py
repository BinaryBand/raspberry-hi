"""Check coverage of setup playbook roles by tests under tests/roles/."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import yaml

_CONFIG = Path("config/lint.toml")
_SETUP_PLAYBOOK = Path("ansible/playbooks/setup.yml")
_TESTS_DIR = Path("tests/roles")


def _expected_test_file(role_name: str) -> Path:
    """Return the expected test file path for *role_name*."""
    sanitised = role_name.replace("-", "_")
    return _TESTS_DIR / f"test_{sanitised}.py"


def _setup_roles() -> list[str]:
    """Extract role names from ansible/playbooks/setup.yml."""
    loaded = yaml.safe_load(_SETUP_PLAYBOOK.read_text(encoding="utf-8"))
    if not isinstance(loaded, list) or not loaded:
        return []

    roles = loaded[0].get("roles", [])
    found: list[str] = []
    for role_item in roles:
        role_name = role_item.get("role") if isinstance(role_item, dict) else None
        if isinstance(role_name, str) and role_name:
            found.append(role_name)
    return found


def main() -> None:
    """Report setup-role test coverage and enforce configured floor."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    floor: int = cfg.get("ansible_roles_coverage", {}).get("floor", 0)

    roles = sorted(_setup_roles())
    covered = [r for r in roles if _expected_test_file(r).exists()]
    missing = [r for r in roles if r not in covered]

    total = len(roles)
    pct = int(100 * len(covered) / total) if total else 100

    print(f"Ansible setup-role test coverage: {len(covered)}/{total} ({pct}%)")
    if covered:
        for role in covered:
            print(f"  [ok]      {role}")
    if missing:
        for role in missing:
            print(f"  [missing] {role}  -> {_expected_test_file(role)}")

    if pct < floor:
        print(f"\nFAIL: coverage {pct}% is below the floor of {floor}%")
        sys.exit(1)

    if missing:
        print(
            f"\nWARNING: {len(missing)} role(s) have no test file (coverage meets floor {floor}%)"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
