"""Tests for the vault CLI commands."""

from __future__ import annotations

import argparse

import pytest

from linux_hi.cli import vault


def test_vault_list_shows_keys(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """cmd_list must display top-level vault keys without showing values."""
    fake_data = {"become_passwords": {"rpi": "secret"}, "rclone_config": {"remote": {"type": "s3"}}}
    monkeypatch.setattr(
        "linux_hi.cli.vault.decrypt_vault_raw",
        lambda: fake_data,
    )
    vault.cmd_list(argparse.Namespace())
    captured = capsys.readouterr()
    assert "become_passwords" in captured.out
    assert "rclone_config" in captured.out
    assert "secret" not in captured.out


def test_cmd_add_exits_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_add should abort when no key is provided through args/env/prompt."""
    monkeypatch.delenv("NAME", raising=False)
    monkeypatch.setattr(
        vault.questionary,
        "text",
        lambda *_a, **_k: type("Q", (), {"ask": lambda self: ""})(),
    )

    with pytest.raises(SystemExit) as exc:
        vault.cmd_add(argparse.Namespace(name=None))

    assert str(exc.value) == "Aborted."


def test_cmd_add_exits_when_value_prompt_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_add should abort when password prompt returns None."""
    monkeypatch.setattr(
        vault.questionary,
        "password",
        lambda *_a, **_k: type("Q", (), {"ask": lambda self: None})(),
    )

    with pytest.raises(SystemExit) as exc:
        vault.cmd_add(argparse.Namespace(name="token"))

    assert str(exc.value) == "Aborted."


def test_cmd_add_writes_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_add should call write_vault_key with prompted value."""
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        vault.questionary,
        "password",
        lambda *_a, **_k: type("Q", (), {"ask": lambda self: "secret"})(),
    )
    monkeypatch.setattr(vault, "write_vault_key", lambda key, value: calls.append((key, value)))

    vault.cmd_add(argparse.Namespace(name="api_key"))

    assert calls == [("api_key", "secret")]


def test_cmd_remove_exits_when_vault_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_remove should fail fast when vault has no top-level keys."""
    monkeypatch.setattr(vault, "decrypt_vault_raw", lambda: {})

    with pytest.raises(SystemExit) as exc:
        vault.cmd_remove(argparse.Namespace(name=None))

    assert str(exc.value) == "Vault is empty."


def test_cmd_remove_aborts_on_prompt_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_remove should abort when key selection prompt is cancelled."""
    monkeypatch.setattr(vault, "decrypt_vault_raw", lambda: {"a": 1})
    monkeypatch.delenv("NAME", raising=False)
    monkeypatch.setattr(
        vault.questionary,
        "select",
        lambda *_a, **_k: type("Q", (), {"ask": lambda self: ""})(),
    )

    with pytest.raises(SystemExit) as exc:
        vault.cmd_remove(argparse.Namespace(name=None))

    assert str(exc.value) == "Aborted."


def test_cmd_remove_calls_remove_vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_remove should delegate deletion to remove_vault_key."""
    removed: list[str] = []
    monkeypatch.setattr(vault, "decrypt_vault_raw", lambda: {"a": 1, "b": 2})
    monkeypatch.setattr(vault, "remove_vault_key", lambda key: removed.append(key))

    vault.cmd_remove(argparse.Namespace(name="b"))

    assert removed == ["b"]


def test_main_dispatches_add(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should dispatch parsed add subcommand to cmd_add."""
    called: list[str] = []
    monkeypatch.setattr(vault, "cmd_add", lambda _args: called.append("add"))

    vault.main(["add", "--name", "x"])

    assert called == ["add"]
