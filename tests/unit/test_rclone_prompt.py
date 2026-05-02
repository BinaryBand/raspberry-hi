"""Unit tests for rclone remote prompt adapter."""

from __future__ import annotations

import pytest

from linux_hi.adapters.rclone_prompt import RcloneRemoteHandler


class _VaultSecrets:
    """Minimal vault object carrying rclone_config for adapter tests."""

    def __init__(self, rclone_config: dict[str, dict[str, str]] | None) -> None:
        """Store rclone config map used by prompt handler."""
        self.rclone_config = rclone_config


def test_prompt_exits_when_no_remotes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt should exit non-zero when vault has no configured remotes."""
    monkeypatch.setattr(
        "linux_hi.services.vault.decrypt_vault",
        lambda: _VaultSecrets(rclone_config={}),
    )
    monkeypatch.setattr("linux_hi.storage.rclone.list_remotes", lambda _cfg: [])

    with pytest.raises(SystemExit) as exc:
        RcloneRemoteHandler().prompt("Select remote", "")

    assert exc.value.code == 1


def test_prompt_returns_selected_remote_and_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt should return the selected remote combined with the entered path."""
    monkeypatch.setattr(
        "linux_hi.services.vault.decrypt_vault",
        lambda: _VaultSecrets(rclone_config={"pcloud": {"type": "pcloud"}}),
    )
    monkeypatch.setattr("linux_hi.storage.rclone.list_remotes", lambda _cfg: ["pcloud", "backup"])
    monkeypatch.setattr(
        "linux_hi.adapters.rclone_prompt.questionary.select",
        lambda _label, choices: type("Q", (), {"ask": lambda self: choices[1]})(),
    )
    monkeypatch.setattr(
        "linux_hi.adapters.rclone_prompt.questionary.text",
        lambda _label, default="": type("Q", (), {"ask": lambda self: "movies"})(),
    )

    selected = RcloneRemoteHandler().prompt("Select remote", "")

    assert selected == "backup:movies"


def test_prompt_normalises_blank_path_to_remote_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank path input should resolve to the selected remote root."""
    monkeypatch.setattr(
        "linux_hi.services.vault.decrypt_vault",
        lambda: _VaultSecrets(rclone_config={"pcloud": {"type": "pcloud"}}),
    )
    monkeypatch.setattr("linux_hi.storage.rclone.list_remotes", lambda _cfg: ["pcloud"])
    monkeypatch.setattr(
        "linux_hi.adapters.rclone_prompt.questionary.select",
        lambda _label, choices: type("Q", (), {"ask": lambda self: choices[0]})(),
    )
    monkeypatch.setattr(
        "linux_hi.adapters.rclone_prompt.questionary.text",
        lambda _label, default="": type("Q", (), {"ask": lambda self: "  /  "})(),
    )

    selected = RcloneRemoteHandler().prompt("Select remote", "")

    assert selected == "pcloud:"
