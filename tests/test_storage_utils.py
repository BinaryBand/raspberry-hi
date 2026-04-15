"""Tests for storage_utils — pure logic and SSH-stub variants."""

from __future__ import annotations

import pytest

from scripts.utils.storage_utils import (
    SYSTEM_MOUNT_PREFIXES,
    SYSTEM_MOUNTS,
    external_mounts,
    get_block_devices,
    get_external_devices,
    get_real_mounts,
    mount_covering,
)
from tests.support.builders import mnt
from tests.support.connections import FakeConnection
from tests.support.data import FINDMNT_OUTPUT, LSBLK_OUTPUT


# ---------------------------------------------------------------------------
# external_mounts
# ---------------------------------------------------------------------------


class TestExternalMounts:
    def test_excludes_root(self):
        assert external_mounts([mnt("/")]) == []

    def test_excludes_boot_partitions(self):
        assert external_mounts([mnt("/boot"), mnt("/boot/firmware")]) == []

    @pytest.mark.parametrize("prefix", SYSTEM_MOUNT_PREFIXES)
    def test_excludes_virtual_filesystems(self, prefix):
        assert external_mounts([mnt(f"{prefix}/something")]) == []

    def test_includes_user_mount(self):
        result = external_mounts([mnt("/mnt/usb")])
        assert len(result) == 1
        assert result[0].target == "/mnt/usb"

    def test_mixed_list(self):
        mounts = [mnt("/"), mnt("/boot"), mnt("/mnt/usb"), mnt("/run/lock"), mnt("/media/disk")]
        targets = [m.target for m in external_mounts(mounts)]
        assert targets == ["/mnt/usb", "/media/disk"]

    def test_empty_list(self):
        assert external_mounts([]) == []

    def test_swap_excluded(self):
        assert external_mounts([mnt("[SWAP]")]) == []


# ---------------------------------------------------------------------------
# mount_covering
# ---------------------------------------------------------------------------


class TestMountCovering:
    def test_falls_back_to_root(self):
        assert mount_covering([mnt("/")], "/mnt/data") == "/"

    def test_exact_match(self):
        assert mount_covering([mnt("/"), mnt("/mnt/usb")], "/mnt/usb") == "/mnt/usb"

    def test_child_path_uses_parent_mount(self):
        assert mount_covering([mnt("/"), mnt("/mnt/usb")], "/mnt/usb/minio/data") == "/mnt/usb"

    def test_most_specific_wins(self):
        mounts = [mnt("/"), mnt("/mnt"), mnt("/mnt/usb")]
        assert mount_covering(mounts, "/mnt/usb/data") == "/mnt/usb"

    def test_no_false_prefix_match(self):
        # /mnt/usb must NOT cover /mnt/usbother
        assert mount_covering([mnt("/"), mnt("/mnt/usb")], "/mnt/usbother/data") == "/"

    def test_trailing_slash_on_mount_point(self):
        from models import MountInfo
        mounts = [mnt("/"), MountInfo(target="/mnt/usb/", source="sda1", fstype="ext4", size="1G")]
        assert mount_covering(mounts, "/mnt/usb/data") == "/mnt/usb/"


# ---------------------------------------------------------------------------
# get_real_mounts
# ---------------------------------------------------------------------------


class TestGetRealMounts:
    def test_returns_all_mounts(self, findmnt_conn):
        assert len(get_real_mounts(findmnt_conn)) == 4

    def test_usb_mount_present(self, findmnt_conn):
        targets = [m.target for m in get_real_mounts(findmnt_conn)]
        assert "/mnt/usb" in targets

    def test_returns_empty_on_failed_command(self):
        conn = FakeConnection({"findmnt": ("", False)})
        assert get_real_mounts(conn) == []

    def test_returns_empty_on_blank_stdout(self):
        conn = FakeConnection({"findmnt": ("   ", True)})
        assert get_real_mounts(conn) == []

    def test_mount_info_fields_populated(self, findmnt_conn):
        usb = next(m for m in get_real_mounts(findmnt_conn) if m.target == "/mnt/usb")
        assert usb.source == "/dev/sda1"
        assert usb.fstype == "ext4"
        assert usb.size == "1T"


# ---------------------------------------------------------------------------
# get_block_devices + get_external_devices
# ---------------------------------------------------------------------------


class TestGetBlockDevices:
    def test_returns_all_top_level_devices(self, lsblk_conn):
        assert len(get_block_devices(lsblk_conn)) == 2

    def test_children_are_parsed(self, lsblk_conn):
        sd_card = get_block_devices(lsblk_conn)[0]
        assert sd_card.children is not None
        assert len(sd_card.children) == 2


class TestGetExternalDevices:
    def test_excludes_system_disk(self, lsblk_conn):
        names = [d.name for d in get_external_devices(get_block_devices(lsblk_conn))]
        assert "mmcblk0p1" not in names
        assert "mmcblk0p2" not in names

    def test_includes_usb_partition(self, lsblk_conn):
        names = [d.name for d in get_external_devices(get_block_devices(lsblk_conn))]
        assert "sda1" in names
