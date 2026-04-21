"""
repo_policy_check.py: CLI entry point for repository architectural policy checks.
"""

import os
import sys
from typing import List

from linux_hi.policy_utils import (
    check_app_dirs,
    check_app_tests,
    check_playbook_vars,
    check_registry_entries,
    get_app_roles,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS_DIR = os.path.join(ROOT, "ansible", "apps")
REGISTRY_PATH = os.path.join(ROOT, "ansible", "registry.yml")
TESTS_DIR = os.path.join(ROOT, "tests")
E2E_DIR = os.path.join(TESTS_DIR, "e2e")


def main() -> None:
    """Run all repo policy checks and print results."""
    failures: List[str] = []
    app_roles = get_app_roles(APPS_DIR)
    check_registry_entries(app_roles, REGISTRY_PATH, failures)
    check_app_dirs(app_roles, APPS_DIR, failures)
    check_app_tests(app_roles, TESTS_DIR, E2E_DIR, failures)
    check_playbook_vars(os.path.join(ROOT, "ansible"), failures)
    if failures:
        print("\nREPO POLICY CHECK FAILED:")
        for fail in failures:
            print(f"- {fail}")
        sys.exit(1)
    print("All repo policy checks passed.")


if __name__ == "__main__":
    main()
