"""CLI entrypoint for repository architectural policy checks."""

from __future__ import annotations

import sys

from linux_hi.policy_utils import (
    check_app_data_paths,
    check_app_dirs,
    check_app_tests,
    check_deleted_compatibility_namespaces,
    check_makefile_guard_checks,
    check_makefile_host_selector,
    check_makefile_phony_and_style,
    check_no_direct_host_group_writes,
    check_playbook_vars,
    check_policy_contract_integrity,
    check_policy_registry_controls,
    check_registry_conflicts,
    check_registry_entries,
    check_scripts_wrapper_topology,
    check_site_become_password_assertion,
    get_app_roles,
)
from models import ANSIBLE_DATA

_ROOT = ANSIBLE_DATA.root
_APPS_DIR = str(_ROOT / "ansible" / "apps")
_REGISTRY_PATH = str(_ROOT / "ansible" / "registry.yml")
_TESTS_DIR = str(_ROOT / "tests")
_E2E_DIR = str(_ROOT / "tests" / "e2e")
_POLICY_REGISTRY = str(_ROOT / "docs" / "POLICY_CONTRACT.yml")


def main() -> None:
    """Run all repo policy checks and print results."""
    failures: list[str] = []
    app_roles = get_app_roles(_APPS_DIR)
    check_registry_entries(app_roles, _REGISTRY_PATH, failures)
    check_app_dirs(app_roles, _APPS_DIR, failures, _REGISTRY_PATH)
    check_registry_conflicts(app_roles, _APPS_DIR, _REGISTRY_PATH, failures)
    check_app_tests(app_roles, _TESTS_DIR, _E2E_DIR, failures)
    check_playbook_vars(str(_ROOT / "ansible"), failures)
    check_site_become_password_assertion(str(_ROOT / "ansible" / "site.yml"), failures)
    check_app_data_paths(app_roles, _REGISTRY_PATH, failures)
    check_deleted_compatibility_namespaces(str(_ROOT), failures)
    check_scripts_wrapper_topology(str(_ROOT), failures)
    check_policy_registry_controls(_POLICY_REGISTRY, failures)
    check_policy_contract_integrity(_POLICY_REGISTRY, failures)
    check_makefile_host_selector(str(_ROOT / "Makefile"), failures)
    check_makefile_guard_checks(str(_ROOT / "Makefile"), failures)
    check_makefile_phony_and_style(str(_ROOT / "Makefile"), app_roles, failures)
    check_no_direct_host_group_writes(str(_ROOT), failures)
    if failures:
        print("\nREPO POLICY CHECK FAILED:")
        for fail in failures:
            print(f"- {fail}")
        sys.exit(1)
    print("All repo policy checks passed.")


if __name__ == "__main__":
    main()
