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


class _Store:
    """Minimal ANSIBLE_DATA substitute exposing host_vars."""

    def host_vars(self, _hostname: str) -> object:
        """Return an opaque host vars object for connection factory wiring."""
        return object()


@dataclass
class _OrchestratorDouble:
    """Mount orchestrator double that returns a configured selection result."""

    result: tuple[str, str] | None

    def mount_new_device(self, _conn: object) -> tuple[str, str] | None:
        """Return the preconfigured mount selection result."""
        return self.result


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


def _patch_mount_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    orchestrator: _OrchestratorDouble,
    conn: _Conn,
    uuid: str | None = "uuid-123",
) -> None:
    """Patch mount CLI runtime dependencies with deterministic test doubles."""
    monkeypatch.setenv("HOST", "rpi")
    monkeypatch.setattr(mount, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(mount, "_become_password", lambda _h: "pw")
    monkeypatch.setattr(mount, "make_connection", lambda _hv, become_password: conn)
    monkeypatch.setattr(mount, "MountOrchestrator", lambda **_kwargs: orchestrator)
    monkeypatch.setattr(mount, "get_device_uuid", lambda _conn, _dev: uuid)


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
    _patch_mount_runtime(
        monkeypatch,
        orchestrator=_OrchestratorDouble(result=None),
        conn=_Conn(),
    )

    with pytest.raises(SystemExit) as exc:
        mount.main()

    assert str(exc.value) == "No device selected."


def test_main_exits_when_label_sanitizes_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should fail when label sanitization yields an empty mount name."""
    _patch_mount_runtime(
        monkeypatch,
        orchestrator=_OrchestratorDouble(result=("/dev/sdb1", "###")),
        conn=_Conn(),
    )

    with pytest.raises(SystemExit) as exc:
        mount.main()

    assert "Invalid mount label" in str(exc.value)


def test_main_appends_uuid_fstab_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should append a UUID-based fstab entry when UUID is available and absent."""
    conn = _Conn(fstab="proc /proc proc defaults 0 0\n")

    _patch_mount_runtime(
        monkeypatch,
        orchestrator=_OrchestratorDouble(result=("/dev/sdb1", "usb")),
        conn=conn,
        uuid="uuid-123",
    )

    mount.main()

    assert any(cmd.startswith("mkdir -p /mnt/usb") for cmd in conn.sudo_calls)
    assert any(cmd.startswith("mount /dev/sdb1 /mnt/usb") for cmd in conn.sudo_calls)
    assert conn.appended == ["UUID=uuid-123 /mnt/usb auto defaults,nofail 0 0\n"]


def test_main_skips_fstab_append_when_uuid_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Main should not append duplicate UUID entries to /etc/fstab."""
    conn = _Conn(fstab="UUID=uuid-123 /mnt/usb auto defaults,nofail 0 0\n")

    _patch_mount_runtime(
        monkeypatch,
        orchestrator=_OrchestratorDouble(result=("/dev/sdb1", "usb")),
        conn=conn,
        uuid="uuid-123",
    )

    mount.main()

    assert conn.appended == []
