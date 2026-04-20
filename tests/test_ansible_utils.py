"""Tests for shared Ansible utility helpers."""

from __future__ import annotations

from typing import Any

import pytest

from models import HostVars
from scripts.utils import ansible_utils


def test_make_connection_uses_relative_ssh_key_from_repo_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative SSH key paths should be resolved against the repository root."""
    captured: dict[str, Any] = {}

    class FakeConnection:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(ansible_utils, "Connection", FakeConnection)

    host = HostVars(
        ansible_host="example.local",
        ansible_user="owen",
        ansible_port=2202,
        ansible_ssh_private_key_file="config/.id_ed25519",
    )

    ansible_utils.make_connection(host)

    assert captured["host"] == "example.local"
    assert captured["user"] == "owen"
    assert captured["port"] == 2202
    assert captured["connect_kwargs"]["key_filename"] == str(
        ansible_utils.ROOT / "config/.id_ed25519"
    )
    assert captured["config"] is None


def test_make_connection_can_configure_sudo_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sudo password should be forwarded into Fabric config when requested."""
    captured: dict[str, Any] = {}

    class FakeConnection:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(ansible_utils, "Connection", FakeConnection)

    host = HostVars(ansible_host="example.local", ansible_user="owen")
    sudo_value = "mount-sudo-value"
    ansible_utils.make_connection(host, become_password=sudo_value)

    assert captured["config"] is not None
    assert captured["config"].sudo.password == sudo_value
