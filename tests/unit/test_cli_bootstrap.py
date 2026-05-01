"""Unit tests for bootstrap CLI flows."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.cli import bootstrap


def test_prompt_missing_become_passwords_returns_empty_when_complete() -> None:
    """Prompt helper should return no updates when all hosts already have passwords."""
    existing = {"rpi": "x", "debian": "y"}
    hosts = ["rpi", "debian"]

    assert bootstrap.prompt_missing_become_passwords(existing, hosts) == {}


def test_prompt_missing_become_passwords_retries_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt helper should retry until a non-empty password is entered."""
    answers = iter(["", "pw"])
    monkeypatch.setattr(bootstrap.getpass, "getpass", lambda _prompt: next(answers))

    updates = bootstrap.prompt_missing_become_passwords({}, ["rpi"])

    assert updates == {"rpi": "pw"}


def test_main_no_changes_when_all_passwords_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should not write vault when prompt helper returns no new passwords."""
    calls: list[str] = []

    monkeypatch.setattr(bootstrap, "setup_vault_password", lambda: calls.append("setup"))
    monkeypatch.setattr(bootstrap, "decrypt_vault_raw", lambda: {"become_passwords": {"rpi": "pw"}})
    monkeypatch.setattr(bootstrap.ANSIBLE_DATA, "inventory_hosts", lambda: ["rpi"])
    monkeypatch.setattr(bootstrap, "prompt_missing_become_passwords", lambda *_a, **_k: {})
    monkeypatch.setattr(bootstrap, "encrypt_vault", lambda _d: calls.append("encrypt"))

    bootstrap.main()

    assert calls == ["setup"]


def test_main_merges_and_encrypts_new_passwords(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Main should merge prompted become passwords into vault payload and encrypt."""
    encrypted: list[dict[str, object]] = []

    monkeypatch.setattr(bootstrap, "setup_vault_password", lambda: None)
    vault_file = tmp_path / "vault.yml"
    vault_file.write_text("encrypted", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "VAULT_FILE", vault_file)
    monkeypatch.setattr(
        bootstrap,
        "decrypt_vault_raw",
        lambda: {"become_passwords": {"debian": "existing"}, "other": "value"},
    )
    monkeypatch.setattr(bootstrap.ANSIBLE_DATA, "inventory_hosts", lambda: ["debian", "rpi"])
    monkeypatch.setattr(
        bootstrap,
        "prompt_missing_become_passwords",
        lambda *_a, **_k: {"rpi": "new"},
    )
    monkeypatch.setattr(bootstrap, "encrypt_vault", lambda data: encrypted.append(data))

    bootstrap.main()

    assert encrypted
    payload = encrypted[-1]
    assert payload["other"] == "value"
    assert payload["become_passwords"] == {"debian": "existing", "rpi": "new"}
