"""Tests for storage_flows — pure functions and questionary-mocked interactive flows."""

from __future__ import annotations

import json
from unittest.mock import patch

from scripts.utils.storage_flows import (
    flow_mount_new_device,
    flow_use_existing_mount,
    parse_path_hints,
)
from tests.support.builders import mnt, partition
from tests.support.connections import FakeConnection

# ---------------------------------------------------------------------------
# parse_path_hints
# ---------------------------------------------------------------------------


class TestParsePathHints:
    """Test suite for path parsing utility."""

    def test_extracts_label_and_subdir(self):
        """Verify extraction of label and subdirectory."""
        assert parse_path_hints("/mnt/minio/minio/data") == ("minio", "minio/data")

    def test_label_only_when_path_ends_at_mount(self):
        """Verify label extraction when path matches mount point."""
        assert parse_path_hints("/mnt/usb") == ("usb", None)

    def test_non_mnt_path_returns_none_none(self):
        """Verify non-mnt path returns (None, None)."""
        assert parse_path_hints("/srv/minio/data") == (None, None)

    def test_root_returns_none_none(self):
        """Verify root path returns (None, None)."""
        assert parse_path_hints("/") == (None, None)

    def test_deep_subdir_preserved(self):
        """Verify deep subdirectory paths are preserved."""
        label, subdir = parse_path_hints("/mnt/storage/minio/data/buckets")
        assert label == "storage"
        assert subdir == "minio/data/buckets"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A connection that returns only system disks — no external devices.
_SYSTEM_ONLY_LSBLK = json.dumps(
    {
        "blockdevices": [
            {
                "name": "mmcblk0",
                "size": "32G",
                "type": "disk",
                "mountpoint": None,
                "label": None,
                "fstype": None,
                "children": [
                    {
                        "name": "mmcblk0p1",
                        "size": "500M",
                        "type": "part",
                        "mountpoint": "/boot/firmware",
                        "label": "bootfs",
                        "fstype": "vfat",
                    },
                    {
                        "name": "mmcblk0p2",
                        "size": "31G",
                        "type": "part",
                        "mountpoint": "/",
                        "label": "rootfs",
                        "fstype": "ext4",
                    },
                ],
            }
        ]
    }
)

# The external partition returned by LSBLK_OUTPUT after device filtering.
_USB_PARTITION = partition("sda1", mountpoint="/mnt/usb", fstype="ext4", label="storage")


# ---------------------------------------------------------------------------
# flow_mount_new_device
# ---------------------------------------------------------------------------


class TestFlowMountNewDevice:
    """Test suite for the interactive new-device mount flow."""

    def test_returns_none_when_no_external_devices(self):
        """Verify None is returned when no external devices are found."""
        conn = FakeConnection({"lsblk": _SYSTEM_ONLY_LSBLK})
        assert flow_mount_new_device(conn) is None

    @patch("scripts.utils.storage_flows.questionary")
    def test_mounts_selected_device(self, mock_q, lsblk_conn):
        """Verify (device_path, label) tuple returned on successful selection."""
        mock_q.select.return_value.ask.return_value = _USB_PARTITION
        mock_q.text.return_value.ask.return_value = "myusb"

        result = flow_mount_new_device(lsblk_conn)

        assert result == ("/dev/sda1", "myusb")

    @patch("scripts.utils.storage_flows.questionary")
    def test_returns_none_when_device_selection_cancelled(self, mock_q, lsblk_conn):
        """Verify None is returned when user cancels device selection."""
        mock_q.select.return_value.ask.return_value = None
        assert flow_mount_new_device(lsblk_conn) is None

    @patch("scripts.utils.storage_flows.questionary")
    def test_returns_none_when_label_cancelled(self, mock_q, lsblk_conn):
        """Verify None is returned when user cancels label input."""
        mock_q.select.return_value.ask.return_value = _USB_PARTITION
        mock_q.text.return_value.ask.return_value = None
        assert flow_mount_new_device(lsblk_conn) is None

    @patch("scripts.utils.storage_flows.questionary")
    def test_label_hint_used_as_default(self, mock_q, lsblk_conn):
        """Verify label_hint is passed as default to the label prompt."""
        mock_q.select.return_value.ask.return_value = _USB_PARTITION
        mock_q.text.return_value.ask.return_value = "hinted"

        flow_mount_new_device(lsblk_conn, label_hint="hinted")

        _, kwargs = mock_q.text.call_args
        assert kwargs.get("default") == "hinted"


# ---------------------------------------------------------------------------
# flow_use_existing_mount
# ---------------------------------------------------------------------------


class TestFlowUseExistingMount:
    """Test suite for the existing-mount selection flow."""

    def test_returns_none_when_no_external_mounts(self):
        """Verify None is returned when no external mounts exist."""
        system_mounts = [mnt("/"), mnt("/boot/firmware")]
        assert flow_use_existing_mount(system_mounts) is None

    @patch("scripts.utils.storage_flows.questionary")
    def test_returns_selected_target(self, mock_q):
        """Verify the selected mount target is returned."""
        mock_q.select.return_value.ask.return_value = "/mnt/usb"
        mounts = [mnt("/"), mnt("/mnt/usb")]

        result = flow_use_existing_mount(mounts)

        assert result == "/mnt/usb"

    @patch("scripts.utils.storage_flows.questionary")
    def test_returns_none_when_selection_cancelled(self, mock_q):
        """Verify None is returned when user cancels selection."""
        mock_q.select.return_value.ask.return_value = None
        mounts = [mnt("/"), mnt("/mnt/usb")]

        assert flow_use_existing_mount(mounts) is None

    @patch("scripts.utils.storage_flows.questionary.select")
    def test_only_external_mounts_offered(self, mock_select):
        """Verify system mounts are excluded from the selection choices.

        Patch only questionary.select — leaving questionary.Choice real — so
        c.value is the actual string, not a Mock attribute.
        """
        mock_select.return_value.ask.return_value = "/mnt/usb"
        mounts = [mnt("/"), mnt("/boot"), mnt("/mnt/usb"), mnt("/run/lock")]

        flow_use_existing_mount(mounts)

        _, kwargs = mock_select.call_args
        offered = [c.value for c in kwargs["choices"]]
        assert offered == ["/mnt/usb"]
