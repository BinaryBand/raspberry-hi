"""Tests for the MountOrchestrator orchestration logic.

These tests use small typed fakes for the InfoPort and Prompter so the
control-flow can be exercised without performing any I/O.
"""

from __future__ import annotations

from models import BlockDevice, MountInfo
from scripts.internal.mount_orchestrator import MountOrchestrator
from scripts.utils.connection_types import RemoteConnection
from tests.support.connections import FakeConnection


class FakeInfo:
    """Minimal InfoPort implementation for orchestration tests."""

    def list_devices(self, conn: RemoteConnection) -> list[BlockDevice]:
        """Return one selectable device."""
        del conn
        return [BlockDevice(name="sdb1", label="usb")]

    def list_mounts(self, conn: RemoteConnection) -> list[MountInfo]:
        """Return no mounts; mount orchestration does not consult mounts yet."""
        del conn
        return []


class FakePrompter:
    """Minimal Prompter implementation for orchestration tests."""

    def choose_device(self, devices: list[BlockDevice]) -> BlockDevice | None:
        """Choose the first discovered device."""
        return devices[0]

    def ask_label(self, default: str | None) -> str | None:
        """Accept the default label chosen by the orchestrator."""
        assert default == "usb"
        return "chosen"


def test_mount_new_device_success() -> None:
    """Verify the orchestrator returns the selected device path and label."""
    conn: RemoteConnection = FakeConnection({})
    orch = MountOrchestrator(
        info=FakeInfo(),
        prompter=FakePrompter(),
    )
    assert orch.mount_new_device(conn=conn) == (
        "/dev/sdb1",
        "chosen",
    )


def test_mount_new_device_no_devices() -> None:
    """Verify the flow stops when discovery returns no external devices."""
    conn: RemoteConnection = FakeConnection({})

    class EmptyInfo(FakeInfo):
        """InfoPort variant that returns no devices."""

        def list_devices(self, conn: RemoteConnection) -> list[BlockDevice]:
            """Return no devices."""
            del conn
            return []

    orch = MountOrchestrator(
        info=EmptyInfo(),
        prompter=FakePrompter(),
    )
    assert orch.mount_new_device(conn=conn) is None


def test_mount_new_device_user_cancels() -> None:
    """Verify the flow stops when the device-selection prompt is cancelled."""
    conn: RemoteConnection = FakeConnection({})

    class CancelPrompter(FakePrompter):
        """Prompter variant that cancels device selection."""

        def choose_device(self, devices: list[BlockDevice]) -> BlockDevice | None:
            """Cancel selection instead of choosing a device."""
            del devices
            return None

    orch = MountOrchestrator(
        info=FakeInfo(),
        prompter=CancelPrompter(),
    )
    assert orch.mount_new_device(conn=conn) is None


def test_label_hint_used_as_default() -> None:
    """Verify an explicit label hint takes precedence over the device label."""
    conn: RemoteConnection = FakeConnection({})

    class HintPrompter(FakePrompter):
        """Prompter variant that expects a caller-supplied label hint."""

        def ask_label(self, default: str | None) -> str | None:
            """Assert the orchestrator forwards the explicit label hint."""
            assert default == "hinted"
            return "hinted"

    orch = MountOrchestrator(
        info=FakeInfo(),
        prompter=HintPrompter(),
    )
    orch.mount_new_device(
        conn=conn,
        label_hint="hinted",
    )
