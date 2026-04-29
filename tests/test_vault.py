"""Tests for the vault CLI commands."""

from __future__ import annotations

import pytest

from linux_hi.cli.vault import cmd_list


def test_vault_list_shows_keys(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """cmd_list must display top-level vault keys without showing values."""
    fake_data = {"become_passwords": {"rpi": "secret"}, "rclone_config": {"remote": {"type": "s3"}}}
    monkeypatch.setattr(
        "linux_hi.cli.vault.decrypt_vault_raw",
        lambda: fake_data,
    )
    cmd_list()
    captured = capsys.readouterr()
    assert "become_passwords" in captured.out
    assert "rclone_config" in captured.out
    assert "secret" not in captured.out
