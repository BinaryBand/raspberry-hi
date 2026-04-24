"""Unit tests for the repository policy check CLI and utilities."""

import os
import tempfile
from pathlib import Path

import linux_hi.policy_utils as rpc

ROOT = Path(__file__).resolve().parents[2]


def test_registry_parsing_skips_metadata() -> None:
    """Ensure registry metadata is not treated as missing app roles."""
    registry_content = """
apps:
    foo:
        service_type: containerized
    bar:
        service_type: tool
"""

    with tempfile.TemporaryDirectory() as tmp:
        reg_path = os.path.join(tmp, "registry.yml")
        with open(reg_path, "w") as file_handle:
            file_handle.write(registry_content)

        failures: list[str] = []
        rpc.check_registry_entries(["foo", "bar"], reg_path, failures)

        assert not failures, f"Unexpected failures: {failures}"


def test_variable_detection_in_playbook() -> None:
    """Ensure playbook-level vars are detected as policy violations."""
    playbook_content = """
---
- name: Example
  hosts: all
  vars:
    my_var: value
"""

    with tempfile.TemporaryDirectory() as tmp:
        ansible_dir = os.path.join(tmp, "ansible")
        os.makedirs(ansible_dir)
        playbook_path = os.path.join(ansible_dir, "playbook.yml")
        with open(playbook_path, "w") as file_handle:
            file_handle.write(playbook_content)

        failures: list[str] = []
        rpc.check_playbook_vars(ansible_dir, failures)

        assert any("playbook.yml" in failure for failure in failures)


def test_no_variable_detection_in_registry() -> None:
    """Ensure registry metadata is skipped by the playbook variable check."""
    registry_content = """
apps:
    foo:
        service_type: containerized
        backup: true
"""

    with tempfile.TemporaryDirectory() as tmp:
        ansible_dir = os.path.join(tmp, "ansible")
        os.makedirs(ansible_dir)
        reg_path = os.path.join(ansible_dir, "registry.yml")
        with open(reg_path, "w") as file_handle:
            file_handle.write(registry_content)

        failures: list[str] = []
        rpc.check_playbook_vars(ansible_dir, failures)

        assert not failures, f"Should not flag registry metadata, got: {failures}"


def test_deleted_compatibility_namespaces_detected() -> None:
    """Ensure reintroduced scripts compatibility namespaces fail policy checks."""
    with tempfile.TemporaryDirectory() as tmp:
        scripts_dir = Path(tmp) / "scripts" / "internal"
        scripts_dir.mkdir(parents=True)

        failures: list[str] = []
        rpc.check_deleted_compatibility_namespaces(tmp, failures)

        assert any("scripts/internal" in failure for failure in failures)


def test_wrapper_topology_detects_non_wrapper_script() -> None:
    """Ensure top-level scripts remain thin linux_hi.cli wrappers."""
    with tempfile.TemporaryDirectory() as tmp:
        scripts_dir = Path(tmp) / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "bootstrap.py").write_text(
            "#!/usr/bin/env python3\n\nprint('not a wrapper')\n",
            encoding="utf-8",
        )

        failures: list[str] = []
        rpc.check_scripts_wrapper_topology(tmp, failures)

        assert any("linux_hi.cli.bootstrap" in failure for failure in failures)


def test_policy_registry_rejects_enforced_policy_without_controls() -> None:
    """Enforced policies must name at least one control target."""
    with tempfile.TemporaryDirectory() as tmp:
        registry = Path(tmp) / "POLICY_CONTRACT.yml"
        registry.write_text(
            """
version: 1
policies:
  - id: demo
    status: enforced
    controls: []
""".lstrip(),
            encoding="utf-8",
        )

        failures: list[str] = []
        rpc.check_policy_registry_controls(str(registry), failures)

        assert any("marked enforced but has no control targets" in failure for failure in failures)


def test_site_requires_always_tagged_become_password_assertion() -> None:
    """The site playbook must keep the always-on become_passwords assertion."""
    site_content = """
---
- name: Provision devices
  hosts: devices
  pre_tasks:
    - name: Verify become password is configured for this host
      ansible.builtin.assert:
        that: (become_passwords | default({})).get(inventory_hostname, '') | length > 0
"""

    with tempfile.TemporaryDirectory() as tmp:
        site_path = Path(tmp) / "site.yml"
        site_path.write_text(site_content.lstrip(), encoding="utf-8")

        failures: list[str] = []
        rpc.check_site_become_password_assertion(str(site_path), failures)

        assert any("tagged 'always'" in failure for failure in failures)


def test_persistent_apps_require_explicit_data_paths() -> None:
    """Persistent apps must declare data paths through registry preflight vars."""
    registry_content = """
apps:
  foo:
    service_type: containerized
    backup: true
    restore: false
    preflight_vars:
      foo_config_path:
        hint: config path
"""

    with tempfile.TemporaryDirectory() as tmp:
        registry_path = Path(tmp) / "registry.yml"
        registry_path.write_text(registry_content.lstrip(), encoding="utf-8")

        failures: list[str] = []
        rpc.check_app_data_paths(["foo"], str(registry_path), failures)

        assert any("*_data_path" in failure for failure in failures)


def test_makefile_runtime_inputs_require_guard_checks() -> None:
    """Runtime Make variables must be guarded with explicit fast-fail checks."""
    makefile_content = """
status:
	ssh host "echo $(SVC)"
"""

    with tempfile.TemporaryDirectory() as tmp:
        makefile_path = Path(tmp) / "Makefile"
        makefile_path.write_text(makefile_content.lstrip(), encoding="utf-8")

        failures: list[str] = []
        rpc.check_makefile_guard_checks(str(makefile_path), failures)

        assert any("$(SVC)" in failure for failure in failures)


def test_direct_host_group_writes_are_rejected_outside_allowed_seams() -> None:
    """Direct writes to host/group vars must stay behind the dedicated helpers."""
    with tempfile.TemporaryDirectory() as tmp:
        writer = Path(tmp) / "writer.py"
        writer.write_text(
            'Path("ansible/inventory/host_vars/rpi.yml").write_text("x")\n',
            encoding="utf-8",
        )

        failures: list[str] = []
        rpc.check_no_direct_host_group_writes(tmp, failures)

        assert any("Direct write to Ansible state" in failure for failure in failures)


def test_makefile_public_targets_require_help_and_kebab_case() -> None:
    """Public .PHONY targets must be kebab-case and visible in help output."""
    makefile_content = """
.PHONY: BadTarget good-target

help:
	@echo "  good-target  ok"
"""

    with tempfile.TemporaryDirectory() as tmp:
        makefile_path = Path(tmp) / "Makefile"
        makefile_path.write_text(makefile_content.lstrip(), encoding="utf-8")

        failures: list[str] = []
        rpc.check_makefile_phony_and_style(str(makefile_path), [], failures)

        assert any("kebab-case" in failure for failure in failures)
        assert any("must appear in make help output" in failure for failure in failures)


def test_registry_role_defaults_conflict_detected() -> None:
    """Conflicting defaults between registry and role defaults should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        apps_dir = Path(tmp) / "ansible" / "apps"
        defaults_dir = apps_dir / "foo" / "defaults"
        defaults_dir.mkdir(parents=True)
        (defaults_dir / "main.yml").write_text(
            "foo_config_path: /role/default\n",
            encoding="utf-8",
        )

        registry_path = Path(tmp) / "ansible" / "registry.yml"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            """
apps:
    foo:
        service_type: containerized
        preflight_vars:
            foo_config_path:
                hint: config path
                default: /registry/default
""".lstrip(),
            encoding="utf-8",
        )

        failures: list[str] = []
        rpc.check_registry_conflicts(["foo"], str(apps_dir), str(registry_path), failures)

        assert any("Registry/role defaults conflict" in f for f in failures)


def test_policy_contract_integrity_detects_missing_references() -> None:
    """Missing semgrep rules / repo-policy functions / make targets should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        policy_path = Path(tmp) / "POLICY_CONTRACT.yml"
        policy_content = (
            "version: 1\n"
            "policies:\n"
            "  - id: p1\n"
            "    status: enforced\n"
            "    controls:\n"
            "      - semgrep:missing-rule\n"
            "      - repo-policy:missing-check\n"
            "      - make:nonexistent-target\n"
        )
        policy_path.write_text(policy_content, encoding="utf-8")

        # Provide a semgrep file that does NOT contain 'missing-rule'
        semgrep_content = "rules:\n  - id: existing-rule\n    message: dummy\n"
        (Path(tmp) / ".semgrep.yml").write_text(semgrep_content, encoding="utf-8")

        failures: list[str] = []
        rpc.check_policy_contract_integrity(str(policy_path), failures)

        assert any(
            "missing-rule" in f or "missing-check" in f or "nonexistent-target" in f
            for f in failures
        )


def test_repo_policy_registry_has_controls_for_all_enforced_policies() -> None:
    """The live policy contract must map enforced architecture rules to controls."""
    failures: list[str] = []
    rpc.check_policy_registry_controls(str(ROOT / "docs" / "POLICY_CONTRACT.yml"), failures)

    assert not failures, f"Unexpected policy coverage failures: {failures}"


def test_live_policy_contract_integrity() -> None:
    """POLICY_CONTRACT.yml controls must reference Semgrep rules, policy_utils, and Make targets."""
    failures: list[str] = []
    rpc.check_policy_contract_integrity(str(ROOT / "docs" / "POLICY_CONTRACT.yml"), failures)

    assert not failures, "Policy contract integrity failures:\n" + "\n".join(failures)
