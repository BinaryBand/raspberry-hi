"""Unit tests for mount CLI flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from linux_hi.cli import mount


class _VaultSecrets:
    """Minimal vault secret model used for mount CLI tests."""

    def __init__(self, become_passwords: dict[str, str] | None) -> None:
        """Store become password mapping."""
        self.become_passwords = become_passwords


@dataclass
class _Conn:
    """Connection double that records sudo invocations and fstab appends."""

    fstab: str = ""
    sudo_calls: list[str] = field(default_factory=list)
    appended: list[str] = field(default_factory=list)

    def sudo(self, command: str, **kwargs: Any) -> Any:
        """Record commands and emulate cat/tee behavior."""
        self.sudo_calls.append(command)
        if command == "cat /etc/fstab":
            return type("R", (), {"stdout": self.fstab})()
        if command == "tee -a /etc/fstab":
            in_stream = kwargs.get("in_stream")
            if in_stream is not None:
                self.appended.append(in_stream.read())
        return type("R", (), {"stdout": ""})()


def test_become_password_reads_from_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    """_become_password should return host password from vault mapping."""
    monkeypatch.setattr(mount, "decrypt_vault", lambda: _VaultSecrets({"rpi": "pw"}))

    assert mount._become_password("rpi") == "pw"


def test_become_password_exits_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """_become_password should exit when no password exists for host."""
    monkeypatch.setattr(mount, "decrypt_vault", lambda: _VaultSecrets({}))

    with pytest.raises(SystemExit) as exc:
        mount._become_password("rpi")

    assert "make bootstrap" in str(exc.value)


def test_main_requires_host_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should exit when HOST is not provided."""
    monkeypatch.delenv("HOST", raising=False)

    with pytest.raises(SystemExit) as exc:
        mount.main()

    assert "HOST is required" in str(exc.value)


def test_main_exits_when_no_device_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should exit when orchestrator returns no selected device."""

    class _Store:
        def host_vars(self, _hostname: str) -> object:
            return object()

    class _Orchestrator:
        def __init__(self, **_kwargs: object) -> None:
            """Construct orchestrator test double."""

        def mount_new_device(self, _conn: object) -> None:
            return None

    monkeypatch.setenv("HOST", "rpi")
    monkeypatch.setattr(mount, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(mount, "_become_password", lambda _h: "pw")
    monkeypatch.setattr(mount, "make_connection", lambda _hv, become_password: _Conn())
    monkeypatch.setattr(mount, "MountOrchestrator", _Orchestrator)

    with pytest.raises(SystemExit) as exc:
        mount.main()

    assert str(exc.value) == "No device selected."


def test_main_exits_when_label_sanitizes_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should fail when label sanitization yields an empty mount name."""

    class _Store:
        def host_vars(self, _hostname: str) -> object:
            return object()

    class _Orchestrator:
        def __init__(self, **_kwargs: object) -> None:
            """Construct orchestrator test double."""

        def mount_new_device(self, _conn: object) -> tuple[str, str]:
            return ("/dev/sdb1", "###")

    monkeypatch.setenv("HOST", "rpi")
    monkeypatch.setattr(mount, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(mount, "_become_password", lambda _h: "pw")
    monkeypatch.setattr(mount, "make_connection", lambda _hv, become_password: _Conn())
    monkeypatch.setattr(mount, "MountOrchestrator", _Orchestrator)

    with pytest.raises(SystemExit) as exc:
        mount.main()

    assert "Invalid mount label" in str(exc.value)


def test_main_appends_uuid_fstab_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should append a UUID-based fstab entry when UUID is available and absent."""

    class _Store:
        def host_vars(self, _hostname: str) -> object:
            return object()

    class _Orchestrator:
        def __init__(self, **_kwargs: object) -> None:
            """Construct orchestrator test double."""

        def mount_new_device(self, _conn: object) -> tuple[str, str]:
            return ("/dev/sdb1", "usb")

    conn = _Conn(fstab="proc /proc proc defaults 0 0\n")

    monkeypatch.setenv("HOST", "rpi")
    monkeypatch.setattr(mount, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(mount, "_become_password", lambda _h: "pw")
    monkeypatch.setattr(mount, "make_connection", lambda _hv, become_password: conn)
    monkeypatch.setattr(mount, "MountOrchestrator", _Orchestrator)
    monkeypatch.setattr(mount, "get_device_uuid", lambda _conn, _dev: "uuid-123")

    mount.main()

    assert any(cmd.startswith("mkdir -p /mnt/usb") for cmd in conn.sudo_calls)
    assert any(cmd.startswith("mount /dev/sdb1 /mnt/usb") for cmd in conn.sudo_calls)
    assert conn.appended == ["UUID=uuid-123 /mnt/usb auto defaults,nofail 0 0\n"]


def test_main_skips_fstab_append_when_uuid_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Main should not append duplicate UUID entries to /etc/fstab."""

    class _Store:
        def host_vars(self, _hostname: str) -> object:
            return object()

    class _Orchestrator:
        def __init__(self, **_kwargs: object) -> None:
            """Construct orchestrator test double."""

        def mount_new_device(self, _conn: object) -> tuple[str, str]:
            return ("/dev/sdb1", "usb")

    conn = _Conn(fstab="UUID=uuid-123 /mnt/usb auto defaults,nofail 0 0\n")

    monkeypatch.setenv("HOST", "rpi")
    monkeypatch.setattr(mount, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(mount, "_become_password", lambda _h: "pw")
    monkeypatch.setattr(mount, "make_connection", lambda _hv, become_password: conn)
    monkeypatch.setattr(mount, "MountOrchestrator", _Orchestrator)
    monkeypatch.setattr(mount, "get_device_uuid", lambda _conn, _dev: "uuid-123")

    mount.main()

    assert conn.appended == []
