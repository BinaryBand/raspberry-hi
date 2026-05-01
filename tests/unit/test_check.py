"""Tests for the package check CLI parsing and vault-only mode."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from linux_hi.cli import check


def _patch_doctor_checks(monkeypatch: pytest.MonkeyPatch, *, python_ok: bool) -> None:
    """Patch doctor-mode checks, toggling only Python result for branch tests."""
    monkeypatch.setattr(check, "_check_python_version", lambda: python_ok)
    monkeypatch.setattr(check, "_check_ansible_available", lambda: True)
    monkeypatch.setattr(check, "_check_ansible_vault_available", lambda: True)
    monkeypatch.setattr(check, "_check_rclone_available", lambda: True)
    monkeypatch.setattr(check, "_check_podman_available", lambda: True)
    monkeypatch.setattr(check, "_check_node_available", lambda: True)
    monkeypatch.setattr(check, "_check_vault_password_file", lambda: True)
    monkeypatch.setattr(check, "_check_hosts_configured", lambda: True)
    monkeypatch.setattr(check, "_check_ssh_key", lambda: True)


def _patch_default_checks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    vault_password_ok: bool,
    vault_secrets: Callable[[], bool],
) -> None:
    """Patch default-mode checks while varying vault password and vault secrets behavior."""
    monkeypatch.setattr(check, "_check_python_version", lambda: True)
    monkeypatch.setattr(check, "_check_ansible_available", lambda: True)
    monkeypatch.setattr(check, "_check_node_available", lambda: True)
    monkeypatch.setattr(check, "_check_vault_password_file", lambda: vault_password_ok)
    monkeypatch.setattr(check, "check_vault_secrets", vault_secrets)
    monkeypatch.setattr(check, "_check_host_reachable", lambda: True)


def test_parse_args_accepts_vault_only_flag() -> None:
    """The vault-only flag should parse as a boolean switch."""
    args = check.parse_args(["--vault-only"])
    assert args.vault_only is True


def test_parse_args_rejects_vault_only_assignment_form() -> None:
    """Unexpected flag values should fail fast instead of silently changing mode."""
    with pytest.raises(SystemExit):
        check.parse_args(["--vault-only=true"])


def test_main_runs_vault_only_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vault-only mode should short-circuit to the vault check path."""
    calls: list[str] = []

    def fake_check_vault_secrets() -> bool:
        calls.append("vault")
        return True

    monkeypatch.setattr(check, "check_vault_secrets", fake_check_vault_secrets)
    check.main(["--vault-only"])

    assert calls == ["vault"]


def test_main_vault_only_exits_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vault-only mode should exit non-zero when vault checks fail."""
    monkeypatch.setattr(check, "check_vault_secrets", lambda: False)

    with pytest.raises(SystemExit) as exc:
        check.main(["--vault-only"])

    assert exc.value.code == 1


def test_main_doctor_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Doctor mode should run all checks and print a success summary."""
    _patch_doctor_checks(monkeypatch, python_ok=True)

    check.main(["--doctor"])

    out = capsys.readouterr().out
    assert "Environment health check" in out
    assert "All environment checks passed." in out


def test_main_doctor_exits_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor mode should exit non-zero when any check fails."""
    _patch_doctor_checks(monkeypatch, python_ok=False)

    with pytest.raises(SystemExit) as exc:
        check.main(["--doctor"])

    assert exc.value.code == 1


def test_main_default_skips_vault_secret_check_when_password_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default mode should not decrypt vault when password file check fails."""
    calls: list[str] = []

    def _vault_secrets() -> bool:
        calls.append("vault")
        return True

    _patch_default_checks(
        monkeypatch,
        vault_password_ok=False,
        vault_secrets=_vault_secrets,
    )

    with pytest.raises(SystemExit) as exc:
        check.main([])

    assert exc.value.code == 1
    assert calls == []


def test_main_default_runs_vault_secret_check_when_password_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default mode should include vault secret validation when password file exists."""
    calls: list[str] = []

    def _vault_secrets() -> bool:
        calls.append("vault")
        return False

    _patch_default_checks(
        monkeypatch,
        vault_password_ok=True,
        vault_secrets=_vault_secrets,
    )

    with pytest.raises(SystemExit) as exc:
        check.main([])

    assert exc.value.code == 1
    assert calls == ["vault"]


def test_check_executable_reports_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """_check_executable should return true when the executable resolves."""
    monkeypatch.setattr(check, "resolve_executable", lambda _name: "/usr/bin/fake")
    assert check._check_executable("fake", "label", "hint") is True


def test_check_executable_reports_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """_check_executable should return false when executable lookup fails."""

    def _missing(_name: str) -> str:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(check, "resolve_executable", _missing)
    assert check._check_executable("fake", "label", "hint") is False


def test_check_host_reachable_handles_runner_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Host reachability should fail cleanly when ansible command execution raises."""

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(check, "run_resolved", _boom)
    assert check._check_host_reachable() is False


def test_check_ssh_key_fails_when_key_file_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSH key check should fail when any configured key path does not exist."""

    class _HostVars:
        def __init__(self, key_file: str | None) -> None:
            self.ansible_ssh_private_key_file = key_file

    class _Store:
        def inventory_hosts(self) -> list[str]:
            return ["rpi", "debian"]

        def host_vars(self, alias: str) -> _HostVars:
            return _HostVars("/does/not/exist") if alias == "rpi" else _HostVars(None)

    monkeypatch.setattr(check, "ANSIBLE_DATA", _Store())
    assert check._check_ssh_key() is False


def test_check_vault_password_file_requires_mode_600(tmp_path: Path) -> None:
    """Vault password file check should require exact 0600 permissions."""
    vault_file = tmp_path / ".vault-password"
    vault_file.write_text("x", encoding="utf-8")
    vault_file.chmod(0o644)

    original = check.VAULT_PASSWORD_FILE
    check.VAULT_PASSWORD_FILE = vault_file
    try:
        assert check._check_vault_password_file() is False
        vault_file.chmod(0o600)
        assert check._check_vault_password_file() is True
    finally:
        check.VAULT_PASSWORD_FILE = original
