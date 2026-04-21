"""E2E connectivity and device discovery tests — require a live Pi.

Run with: make test-e2e
"""

import pytest

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.storage.devices import get_block_devices, get_real_mounts


@pytest.mark.e2e
def test_root_mount_exists(live_conn: RemoteConnection) -> None:
    """Verify root mount is found in real system mounts."""
    mounts = get_real_mounts(live_conn)
    assert any(m.target == "/" for m in mounts), "No root mount found"


@pytest.mark.e2e
def test_real_mounts_have_source_and_fstype(live_conn: RemoteConnection) -> None:
    """Verify real mounts have source and fstype attributes."""
    mounts = get_real_mounts(live_conn)
    assert mounts, "findmnt returned no mounts"
    for m in mounts:
        assert m.source is not None
        assert m.fstype is not None


@pytest.mark.e2e
def test_block_devices_discoverable(live_conn: RemoteConnection) -> None:
    """Verify block devices are discoverable on the live system."""
    devices = get_block_devices(live_conn)
    assert devices, "lsblk returned no devices"
    assert all(d.name for d in devices)


@pytest.mark.e2e
def test_root_device_classified_as_system(live_conn: RemoteConnection) -> None:
    """Verify the disk hosting the root filesystem is classified as a system device."""
    from linux_hi.storage.devices import is_system_device

    devices = get_block_devices(live_conn)
    # Find whichever disk contains a partition mounted at /
    root_disks = [
        d
        for d in devices
        if d.type == "disk" and any(c.mountpoint == "/" for c in (d.children or []))
    ]
    assert root_disks, "No disk found hosting the root partition"
    assert all(is_system_device(d) for d in root_disks)
