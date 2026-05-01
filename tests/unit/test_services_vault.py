"""Unit tests for vault service helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.services import vault


class _Result:
    """Simple process result stub used to fake run_resolved responses."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        """Store process-like return values for assertions."""
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_setup_vault_password_noop_when_file_exists(tmp_path: Path) -> None:
    """setup_vault_password should return immediately when target file already exists."""
    vault_file = tmp_path / ".vault-password"
    vault_file.write_text("already-set", encoding="utf-8")

    vault.setup_vault_password(vault_file)

    assert vault_file.read_text(encoding="utf-8") == "already-set"


def test_setup_vault_password_retries_until_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """setup_vault_password should retry until confirmation matches."""
    answers = iter(["one", "two", "good", "good"])
    monkeypatch.setattr(vault.getpass, "getpass", lambda _prompt: next(answers))

    vault_file = tmp_path / ".vault-password"
    vault.setup_vault_password(vault_file)

    assert vault_file.read_text(encoding="utf-8") == "good"
    assert vault_file.stat().st_mode & 0o777 == 0o600


def test_decrypt_vault_raw_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """decrypt_vault_raw should return parsed mapping when decrypt command succeeds."""
    monkeypatch.setattr(
        vault,
        "run_resolved",
        lambda *_a, **_k: _Result(0, stdout="become_passwords:\n  rpi: secret\n"),
    )

    data = vault.decrypt_vault_raw(tmp_path / "vault.yml", tmp_path / ".vault-password")

    assert data["become_passwords"] == {"rpi": "secret"}


def test_decrypt_vault_raw_exits_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """decrypt_vault_raw should terminate when ansible-vault decrypt fails."""
    monkeypatch.setattr(vault, "run_resolved", lambda *_a, **_k: _Result(1, stderr="boom"))

    with pytest.raises(SystemExit) as exc:
        vault.decrypt_vault_raw()

    assert exc.value.code == 1


def test_encrypt_vault_exits_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """encrypt_vault should terminate when ansible-vault encrypt fails."""
    monkeypatch.setattr(vault, "run_resolved", lambda *_a, **_k: _Result(2, stderr="nope"))

    with pytest.raises(SystemExit) as exc:
        vault.encrypt_vault({"k": "v"})

    assert exc.value.code == 1


def test_write_and_remove_vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """write_vault_key and remove_vault_key should mutate top-level keys correctly."""
    state = {"existing": "x"}
    writes: list[dict[str, object]] = []

    monkeypatch.setattr(vault, "decrypt_vault_raw", lambda: dict(state))
    monkeypatch.setattr(vault, "encrypt_vault", lambda data: writes.append(dict(data)))

    vault.write_vault_key("new_key", "new_value")
    assert writes[-1]["new_key"] == "new_value"

    monkeypatch.setattr(vault, "decrypt_vault_raw", lambda: dict(writes[-1]))
    vault.remove_vault_key("new_key")
    assert "new_key" not in writes[-1]


def test_write_and_remove_become_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """become password helpers should update nested become_passwords mapping."""
    writes: list[dict[str, object]] = []

    monkeypatch.setattr(vault, "decrypt_vault_raw", lambda: {"become_passwords": {"rpi": "old"}})
    monkeypatch.setattr(vault, "encrypt_vault", lambda data: writes.append(dict(data)))

    vault.write_become_password("debian", "new")
    become = writes[-1]["become_passwords"]
    assert isinstance(become, dict)
    assert become["debian"] == "new"

    monkeypatch.setattr(vault, "decrypt_vault_raw", lambda: dict(writes[-1]))
    vault.remove_become_password("rpi")
    become_after = writes[-1]["become_passwords"]
    assert isinstance(become_after, dict)
    assert "rpi" not in become_after
