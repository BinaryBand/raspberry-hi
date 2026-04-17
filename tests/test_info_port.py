"""Tests for the InfoPort adapter in `scripts.utils.info_port`.

Verify that `RemoteInfoPort` delegates to the helpers in
`scripts.utils.storage_utils` so discovery logic is reusable.
"""

from __future__ import annotations

from typing import cast

import pytest

from models import BlockDevice, MountInfo
from scripts.utils.info_port import RemoteInfoPort
from scripts.utils.storage_utils import RemoteConnection
from tests.support.builders import blk, mnt, partition


def test_list_devices_delegates_to_storage_utils(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify device discovery delegates through storage utility helpers."""
    conn = cast(RemoteConnection, object())
    usb_partition = partition("sda1")
    disk = blk("sda", "disk", mountpoint=None, children=[usb_partition])

    def fake_get_block_devices(_conn: RemoteConnection) -> list[BlockDevice]:
        return [disk]

    def fake_get_external_devices(_devices: list[BlockDevice]) -> list[BlockDevice]:
        return [usb_partition]

    monkeypatch.setattr(
        "scripts.utils.storage_utils.get_block_devices",
        fake_get_block_devices,
    )
    monkeypatch.setattr(
        "scripts.utils.storage_utils.get_external_devices",
        fake_get_external_devices,
    )

    rip = RemoteInfoPort()
    assert rip.list_devices(conn) == [usb_partition]


def test_list_mounts_delegates_to_storage_utils(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify mount discovery delegates to the real mount helper."""
    mounts = [mnt("/mnt/usb")]

    def fake_get_real_mounts(_conn: RemoteConnection) -> list[MountInfo]:
        return mounts

    monkeypatch.setattr(
        "scripts.utils.storage_utils.get_real_mounts",
        fake_get_real_mounts,
    )

    rip = RemoteInfoPort()
    assert rip.list_mounts(cast(RemoteConnection, object())) == mounts
