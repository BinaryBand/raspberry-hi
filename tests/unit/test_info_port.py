"""Tests for the InfoPort adapter in `linux_hi.adapters.info_port`.

Verify that `RemoteInfoPort` delegates to the helpers in
`linux_hi.storage` so discovery logic is reusable.
"""

from __future__ import annotations

from typing import cast

import pytest

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.adapters.info_port import RemoteInfoPort
from linux_hi.models import BlockDevice, MountInfo
from tests.support.builders import blk, mnt, partition
from tests.support.connections import FakeConnection


def test_list_devices_delegates_to_storage_utils(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify device discovery delegates through storage utility helpers."""
    conn = cast(RemoteConnection, FakeConnection({}))
    usb_partition = partition("sda1")
    disk = blk("sda", "disk", mountpoint=None, children=[usb_partition])

    def fake_get_block_devices(_conn: RemoteConnection) -> list[BlockDevice]:
        return [disk]

    def fake_get_external_devices(_devices: list[BlockDevice]) -> list[BlockDevice]:
        return [usb_partition]

    monkeypatch.setattr(
        "linux_hi.storage.discovery.get_block_devices",
        fake_get_block_devices,
    )
    monkeypatch.setattr(
        "linux_hi.storage.policy.get_external_devices",
        fake_get_external_devices,
    )

    rip = RemoteInfoPort()
    assert rip.list_devices(conn) == [usb_partition]


def test_list_mounts_delegates_to_storage_utils(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify mount discovery delegates to the real mount helper."""
    mounts = [mnt("/mnt/usb")]
    conn = cast(RemoteConnection, FakeConnection({}))

    def fake_get_real_mounts(_conn: RemoteConnection) -> list[MountInfo]:
        return mounts

    monkeypatch.setattr(
        "linux_hi.storage.discovery.get_real_mounts",
        fake_get_real_mounts,
    )

    rip = RemoteInfoPort()
    assert rip.list_mounts(conn) == mounts
