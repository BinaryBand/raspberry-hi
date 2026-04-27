"""PolicyRunner: coordinates all repository policy checks."""

from __future__ import annotations

import sys
from pathlib import Path

from . import ansible_checks, app_checks, contract_checks, makefile_checks
from ._loader import Failures


class PolicyRunner:
    """Coordinates all repository policy checks against a fixed project root."""

    def __init__(self, root: Path) -> None:
        """Store the repository root; all check paths are derived in run()."""
        self._root = root

    def run(self) -> None:
        """Run all checks and exit non-zero if any fail."""
        root = self._root
        ansible_dir = root / "ansible"
        apps_dir = ansible_dir / "apps"
        registry = ansible_dir / "registry.yml"
        policy_contract = root / "docs" / "POLICY_CONTRACT.yml"
        makefile = root / "Makefile"
        failures: Failures = []
        app_roles = app_checks.get_app_roles(apps_dir)
        app_checks.check_registry_entries(app_roles, registry, failures)
        app_checks.check_app_dirs(app_roles, apps_dir, failures, registry)
        app_checks.check_registry_conflicts(app_roles, apps_dir, registry, failures)
        app_checks.check_app_tests(app_roles, root / "tests", root / "tests" / "e2e", failures)
        ansible_checks.check_playbook_vars(ansible_dir, failures)
        ansible_checks.check_site_become_password_assertion(
            ansible_dir / "playbooks" / "setup.yml", failures
        )
        app_checks.check_app_playbooks(app_roles, apps_dir, failures)
        app_checks.check_app_data_paths(app_roles, registry, failures)
        contract_checks.check_policy_registry_controls(policy_contract, failures)
        contract_checks.check_policy_contract_integrity(policy_contract, failures)
        makefile_checks.check_makefile_host_selector(makefile, failures)
        makefile_checks.check_makefile_guard_checks(makefile, failures)
        makefile_checks.check_makefile_phony_and_style(makefile, app_roles, failures)
        ansible_checks.check_no_direct_host_group_writes(root, failures)
        if failures:
            print("\nREPO POLICY CHECK FAILED:")
            for fail in failures:
                print(f"- {fail}")
            sys.exit(1)
        print("All repo policy checks passed.")
