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


def test_repo_policy_registry_has_controls_for_all_enforced_policies() -> None:
    """The live policy contract must map enforced architecture rules to controls."""
    failures: list[str] = []
    rpc.check_policy_registry_controls(str(ROOT / "docs" / "POLICY_CONTRACT.yml"), failures)

    assert not failures, f"Unexpected policy coverage failures: {failures}"
