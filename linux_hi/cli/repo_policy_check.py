"""CLI entrypoint for repository architectural policy checks."""

from __future__ import annotations

import sys

from linux_hi.policy_utils import (
    check_app_dirs,
    check_app_tests,
    check_playbook_vars,
    check_registry_entries,
    get_app_roles,
)
from models import ANSIBLE_DATA

_ROOT = ANSIBLE_DATA.root
_APPS_DIR = str(_ROOT / "ansible" / "apps")
_REGISTRY_PATH = str(_ROOT / "ansible" / "registry.yml")
_TESTS_DIR = str(_ROOT / "tests")
_E2E_DIR = str(_ROOT / "tests" / "e2e")


def main() -> None:
    """Run all repo policy checks and print results."""
    failures: list[str] = []
    app_roles = get_app_roles(_APPS_DIR)
    check_registry_entries(app_roles, _REGISTRY_PATH, failures)
    check_app_dirs(app_roles, _APPS_DIR, failures)
    check_app_tests(app_roles, _TESTS_DIR, _E2E_DIR, failures)
    check_playbook_vars(str(_ROOT / "ansible"), failures)
    if failures:
        print("\nREPO POLICY CHECK FAILED:")
        for fail in failures:
            print(f"- {fail}")
        sys.exit(1)
    print("All repo policy checks passed.")


if __name__ == "__main__":
    main()
