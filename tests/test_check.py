"""Tests for scripts/check.py CLI parsing and vault-only mode."""

from __future__ import annotations

import pytest

from scripts import check


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
