"""E2E connectivity and device discovery tests — require a live Pi.

Run with: make test-e2e
"""

import pytest

from scripts.utils.storage_utils import get_block_devices, get_real_mounts


@pytest.mark.e2e
def test_root_mount_exists(live_conn):
    mounts = get_real_mounts(live_conn)
    assert any(m.target == "/" for m in mounts), "No root mount found"


@pytest.mark.e2e
def test_real_mounts_have_source_and_fstype(live_conn):
    mounts = get_real_mounts(live_conn)
    assert mounts, "findmnt returned no mounts"
    for m in mounts:
        assert m.source is not None
        assert m.fstype is not None


@pytest.mark.e2e
def test_block_devices_discoverable(live_conn):
    devices = get_block_devices(live_conn)
    assert devices, "lsblk returned no devices"
    assert all(d.name for d in devices)


@pytest.mark.e2e
def test_sd_card_classified_as_system(live_conn):
    from scripts.utils.storage_utils import is_system_device

    devices = get_block_devices(live_conn)
    # The Pi always has mmcblk0 (SD card) as a system device
    sd_cards = [d for d in devices if d.name.startswith("mmcblk")]
    assert sd_cards, "No SD card found"
    assert all(is_system_device(d) for d in sd_cards)
