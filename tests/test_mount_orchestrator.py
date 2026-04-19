"""Tests for the MountOrchestrator orchestration logic.

These tests use small typed fakes for the InfoPort and Prompter so the
control-flow can be exercised without performing any I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from scripts.internal.mount_orchestrator import MountOrchestrator
from scripts.utils.info_port import InfoPort
from scripts.utils.prompter import Prompter
from scripts.utils.storage_utils import RemoteConnection


@dataclass
class DummyDevice:
    """Simple device object with the fields MountOrchestrator needs."""

    name: str
    label: str | None = None


class FakeInfo:
    """Minimal InfoPort implementation for orchestration tests."""

    def list_devices(self, conn: RemoteConnection) -> list[DummyDevice]:
        """Return one selectable device."""
        del conn
        return [DummyDevice("sdb1", "usb")]


class FakePrompter:
    """Minimal Prompter implementation for orchestration tests."""

    def choose_device(self, devices: list[DummyDevice]) -> DummyDevice | None:
        """Choose the first discovered device."""
        return devices[0]

    def ask_label(self, default: str | None) -> str | None:
        """Accept the default label chosen by the orchestrator."""
        assert default == "usb"
        return "chosen"


def test_mount_new_device_success() -> None:
    """Verify the orchestrator returns the selected device path and label."""
    orch = MountOrchestrator(
        info=cast(InfoPort, FakeInfo()),
        prompter=cast(Prompter, FakePrompter()),
    )
    assert orch.mount_new_device(conn=cast(RemoteConnection, object())) == (
        "/dev/sdb1",
        "chosen",
    )


def test_mount_new_device_no_devices() -> None:
    """Verify the flow stops when discovery returns no external devices."""

    class EmptyInfo(FakeInfo):
        """InfoPort variant that returns no devices."""

        def list_devices(self, conn: RemoteConnection) -> list[DummyDevice]:
            """Return no devices."""
            del conn
            return []

    orch = MountOrchestrator(
        info=cast(InfoPort, EmptyInfo()),
        prompter=cast(Prompter, FakePrompter()),
    )
    assert orch.mount_new_device(conn=cast(RemoteConnection, object())) is None


def test_mount_new_device_user_cancels() -> None:
    """Verify the flow stops when the device-selection prompt is cancelled."""

    class CancelPrompter(FakePrompter):
        """Prompter variant that cancels device selection."""

        def choose_device(self, devices: list[DummyDevice]) -> DummyDevice | None:
            """Cancel selection instead of choosing a device."""
            del devices
            return None

    orch = MountOrchestrator(
        info=cast(InfoPort, FakeInfo()),
        prompter=cast(Prompter, CancelPrompter()),
    )
    assert orch.mount_new_device(conn=cast(RemoteConnection, object())) is None


def test_label_hint_used_as_default() -> None:
    """Verify an explicit label hint takes precedence over the device label."""

    class HintPrompter(FakePrompter):
        """Prompter variant that expects a caller-supplied label hint."""

        def ask_label(self, default: str | None) -> str | None:
            """Assert the orchestrator forwards the explicit label hint."""
            assert default == "hinted"
            return "hinted"

    orch = MountOrchestrator(
        info=cast(InfoPort, FakeInfo()),
        prompter=cast(Prompter, HintPrompter()),
    )
    orch.mount_new_device(
        conn=cast(RemoteConnection, object()),
        label_hint="hinted",
    )
