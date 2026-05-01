"""Unit tests for policy runner orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.policy import runner


def test_policy_runner_calls_all_checks_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Runner should invoke each check hook and return accumulated failures."""
    calls: list[str] = []

    def _record(name: str):
        def _inner(*_args: object, **_kwargs: object) -> None:
            calls.append(name)

        return _inner

    monkeypatch.setattr(runner.app_checks, "get_app_roles", lambda _apps_dir: ["synapse"])
    monkeypatch.setattr(
        runner.app_checks,
        "check_registry_entries",
        _record("check_registry_entries"),
    )
    monkeypatch.setattr(runner.app_checks, "check_app_dirs", _record("check_app_dirs"))
    monkeypatch.setattr(
        runner.app_checks,
        "check_registry_conflicts",
        _record("check_registry_conflicts"),
    )
    monkeypatch.setattr(runner.app_checks, "check_app_tests", _record("check_app_tests"))
    monkeypatch.setattr(
        runner.ansible_checks,
        "check_playbook_vars",
        _record("check_playbook_vars"),
    )
    monkeypatch.setattr(
        runner.ansible_checks,
        "check_site_become_password_assertion",
        _record("check_site_become_password_assertion"),
    )
    monkeypatch.setattr(runner.app_checks, "check_app_playbooks", _record("check_app_playbooks"))
    monkeypatch.setattr(
        runner.contract_checks,
        "check_policy_registry_controls",
        _record("check_policy_registry_controls"),
    )
    monkeypatch.setattr(
        runner.contract_checks,
        "check_policy_contract_integrity",
        _record("check_policy_contract_integrity"),
    )
    monkeypatch.setattr(
        runner.makefile_checks,
        "check_makefile_host_selector",
        _record("check_makefile_host_selector"),
    )
    monkeypatch.setattr(
        runner.makefile_checks,
        "check_makefile_guard_checks",
        _record("check_makefile_guard_checks"),
    )
    monkeypatch.setattr(
        runner.makefile_checks,
        "check_makefile_phony_and_style",
        _record("check_makefile_phony_and_style"),
    )

    def _append_failure(_root: Path, failures: list[str]) -> None:
        calls.append("check_no_direct_host_group_writes")
        failures.append("boom")

    monkeypatch.setattr(
        runner.ansible_checks,
        "check_no_direct_host_group_writes",
        _append_failure,
    )

    result = runner.PolicyRunner(tmp_path).run()

    assert calls == [
        "check_registry_entries",
        "check_app_dirs",
        "check_registry_conflicts",
        "check_app_tests",
        "check_playbook_vars",
        "check_site_become_password_assertion",
        "check_app_playbooks",
        "check_policy_registry_controls",
        "check_policy_contract_integrity",
        "check_makefile_host_selector",
        "check_makefile_guard_checks",
        "check_makefile_phony_and_style",
        "check_no_direct_host_group_writes",
    ]
    assert result == ["boom"]


def test_policy_runner_passes_expected_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Runner should derive canonical path arguments from repository root."""
    observed: dict[str, Path] = {}

    def _roles(apps_dir: Path) -> list[str]:
        observed["apps_dir"] = apps_dir
        return []

    def _playbook_vars(ansible_dir: Path, failures: list[str]) -> None:
        del failures
        observed["ansible_dir"] = ansible_dir

    def _site_assert(playbook: Path, failures: list[str]) -> None:
        del failures
        observed["setup_playbook"] = playbook

    def _no_direct(root: Path, failures: list[str]) -> None:
        del failures
        observed["root"] = root

    monkeypatch.setattr(runner.app_checks, "get_app_roles", _roles)
    monkeypatch.setattr(runner.app_checks, "check_registry_entries", lambda *_a: None)
    monkeypatch.setattr(runner.app_checks, "check_app_dirs", lambda *_a: None)
    monkeypatch.setattr(runner.app_checks, "check_registry_conflicts", lambda *_a: None)
    monkeypatch.setattr(runner.app_checks, "check_app_tests", lambda *_a: None)
    monkeypatch.setattr(runner.ansible_checks, "check_playbook_vars", _playbook_vars)
    monkeypatch.setattr(runner.ansible_checks, "check_site_become_password_assertion", _site_assert)
    monkeypatch.setattr(runner.app_checks, "check_app_playbooks", lambda *_a: None)
    monkeypatch.setattr(runner.contract_checks, "check_policy_registry_controls", lambda *_a: None)
    monkeypatch.setattr(runner.contract_checks, "check_policy_contract_integrity", lambda *_a: None)
    monkeypatch.setattr(runner.makefile_checks, "check_makefile_host_selector", lambda *_a: None)
    monkeypatch.setattr(runner.makefile_checks, "check_makefile_guard_checks", lambda *_a: None)
    monkeypatch.setattr(runner.makefile_checks, "check_makefile_phony_and_style", lambda *_a: None)
    monkeypatch.setattr(runner.ansible_checks, "check_no_direct_host_group_writes", _no_direct)

    runner.PolicyRunner(tmp_path).run()

    assert observed["root"] == tmp_path
    assert observed["ansible_dir"] == tmp_path / "ansible"
    assert observed["apps_dir"] == tmp_path / "ansible" / "apps"
    assert observed["setup_playbook"] == tmp_path / "ansible" / "playbooks" / "setup.yml"
