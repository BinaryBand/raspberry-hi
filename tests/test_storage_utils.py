"""Tests for storage_utils — pure logic and SSH-stub variants."""

from __future__ import annotations

import pytest

from linux_hi.storage.devices import (
    SYSTEM_MOUNT_PREFIXES,
    external_mounts,
    get_block_devices,
    get_external_devices,
    get_real_mounts,
    is_system_device,
    mount_covering,
)
from tests.support.builders import blk, mnt
from tests.support.connections import FakeConnection

# ---------------------------------------------------------------------------
# external_mounts
# ---------------------------------------------------------------------------


class TestExternalMounts:
    """Test suite for identifying external storage mounts."""

    def test_excludes_root(self) -> None:
        """Verify root mount is excluded."""
        assert external_mounts([mnt("/")]) == []

    def test_excludes_boot_partitions(self) -> None:
        """Verify boot partitions are excluded."""
        assert external_mounts([mnt("/boot"), mnt("/boot/firmware")]) == []

    @pytest.mark.parametrize("prefix", SYSTEM_MOUNT_PREFIXES)
    def test_excludes_virtual_filesystems(self, prefix: str) -> None:
        """Verify virtual filesystems are excluded."""
        assert external_mounts([mnt(f"{prefix}/something")]) == []

    def test_includes_user_mount(self) -> None:
        """Verify user mount is correctly identified."""
        result = external_mounts([mnt("/mnt/usb")])
        assert len(result) == 1
        assert result[0].target == "/mnt/usb"

    def test_mixed_list(self) -> None:
        """Verify mixed list filtering."""
        mounts = [mnt("/"), mnt("/boot"), mnt("/mnt/usb"), mnt("/run/lock"), mnt("/media/disk")]
        targets = [m.target for m in external_mounts(mounts)]
        assert targets == ["/mnt/usb", "/media/disk"]

    def test_empty_list(self) -> None:
        """Verify empty list input."""
        assert external_mounts([]) == []

    def test_swap_excluded(self) -> None:
        """Verify swap partition is excluded."""
        assert external_mounts([mnt("[SWAP]")]) == []

    def test_supports_custom_mount_policy(self) -> None:
        """Verify callers can override system-mount classification per platform."""

        def custom_policy(target: str | None) -> bool:
            return target in {"/", "/efi"}

        mounts = [mnt("/"), mnt("/boot/firmware"), mnt("/mnt/usb")]
        targets = [m.target for m in external_mounts(mounts, mount_policy=custom_policy)]
        assert targets == ["/boot/firmware", "/mnt/usb"]


# ---------------------------------------------------------------------------
# mount_covering
# ---------------------------------------------------------------------------


class TestMountCovering:
    """Test suite for determining which mount covers a path."""

    def test_falls_back_to_root(self) -> None:
        """Verify fallback to root mount."""
        assert mount_covering([mnt("/")], "/mnt/data") == "/"

    def test_exact_match(self) -> None:
        """Verify exact mount match."""
        assert mount_covering([mnt("/"), mnt("/mnt/usb")], "/mnt/usb") == "/mnt/usb"

    def test_child_path_uses_parent_mount(self) -> None:
        """Verify child path uses parent mount."""
        assert mount_covering([mnt("/"), mnt("/mnt/usb")], "/mnt/usb/minio/data") == "/mnt/usb"

    def test_most_specific_wins(self) -> None:
        """Verify most specific mount wins."""
        mounts = [mnt("/"), mnt("/mnt"), mnt("/mnt/usb")]
        assert mount_covering(mounts, "/mnt/usb/data") == "/mnt/usb"

    def test_no_false_prefix_match(self) -> None:
        """Verify no false prefix match."""
        # /mnt/usb must NOT cover /mnt/usbother
        assert mount_covering([mnt("/"), mnt("/mnt/usb")], "/mnt/usbother/data") == "/"

    def test_trailing_slash_on_mount_point(self) -> None:
        """Verify trailing slash handling."""
        from linux_hi.models import MountInfo

        mounts = [mnt("/"), MountInfo(target="/mnt/usb/", source="sda1", fstype="ext4", size="1G")]
        assert mount_covering(mounts, "/mnt/usb/data") == "/mnt/usb/"


# ---------------------------------------------------------------------------
# get_real_mounts
# ---------------------------------------------------------------------------


class TestGetRealMounts:
    """Test suite for retrieving mount information."""

    def test_returns_all_mounts(self, findmnt_conn: FakeConnection) -> None:
        """Verify all mounts are returned."""
        assert len(get_real_mounts(findmnt_conn)) == 4

    def test_usb_mount_present(self, findmnt_conn: FakeConnection) -> None:
        """Verify USB mount presence."""
        targets = [m.target for m in get_real_mounts(findmnt_conn)]
        assert "/mnt/usb" in targets

    def test_returns_empty_on_failed_command(self) -> None:
        """Verify empty return on command failure."""
        conn = FakeConnection({"findmnt": ("", False)})
        assert get_real_mounts(conn) == []

    def test_returns_empty_on_blank_stdout(self) -> None:
        """Verify empty return on blank output."""
        conn = FakeConnection({"findmnt": ("   ", True)})
        assert get_real_mounts(conn) == []

    def test_mount_info_fields_populated(self, findmnt_conn: FakeConnection) -> None:
        """Verify mount info fields are correctly populated."""
        usb = next(m for m in get_real_mounts(findmnt_conn) if m.target == "/mnt/usb")
        assert usb.source == "/dev/sdb1"
        assert usb.fstype == "ext4"
        assert usb.size == "1T"


# ---------------------------------------------------------------------------
# get_block_devices + get_external_devices
# ---------------------------------------------------------------------------


class TestGetBlockDevices:
    """Test suite for retrieving block devices."""

    def test_returns_all_top_level_devices(self, lsblk_conn: FakeConnection) -> None:
        """Verify all top-level devices are returned."""
        assert len(get_block_devices(lsblk_conn)) == 2

    def test_children_are_parsed(self, lsblk_conn: FakeConnection) -> None:
        """Verify child devices are parsed."""
        system_disk = get_block_devices(lsblk_conn)[0]
        assert system_disk.children is not None
        assert len(system_disk.children) == 2


class TestGetExternalDevices:
    """Test suite for retrieving external devices."""

    def test_excludes_system_disk(self, lsblk_conn: FakeConnection) -> None:
        """Verify system disk is excluded."""
        names = [d.name for d in get_external_devices(get_block_devices(lsblk_conn))]
        assert "sda1" not in names
        assert "sda2" not in names

    def test_includes_usb_partition(self, lsblk_conn: FakeConnection) -> None:
        """Verify USB partition is included."""
        names = [d.name for d in get_external_devices(get_block_devices(lsblk_conn))]
        assert "sdb1" in names

    def test_supports_custom_mount_policy(self) -> None:
        """Verify disk classification can be overridden by a custom policy."""

        def custom_policy(target: str | None) -> bool:
            return target in {"/", "/efi"}

        system_disk = blk(
            "nvme0n1",
            "disk",
            None,
            [
                blk("nvme0n1p1", "part", "/efi", fstype="vfat"),
                blk("nvme0n1p2", "part", "/", fstype="ext4"),
            ],
        )
        data_disk = blk("sdb", "disk", None, [blk("sdb1", "part", "/boot/firmware", fstype="ext4")])

        external = get_external_devices([system_disk, data_disk], mount_policy=custom_policy)
        assert [d.name for d in external] == ["sdb1"]


class TestIsSystemDevice:
    """Test suite for classifying system devices recursively."""

    def test_uses_custom_policy_recursively(self) -> None:
        """Verify custom policy is applied to child partitions too."""

        def custom_policy(target: str | None) -> bool:
            return target in {"/", "/efi"}

        disk = blk("nvme0n1", "disk", None, [blk("nvme0n1p1", "part", "/efi", fstype="vfat")])
        assert is_system_device(disk, mount_policy=custom_policy)
