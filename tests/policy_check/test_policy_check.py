"""Unit tests for the repository policy check CLI and utilities."""

import os
import tempfile

import scripts.repo_policy_check as rpc


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
