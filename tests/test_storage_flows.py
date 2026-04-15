"""Tests for storage_flows — pure functions only.

Interactive flows (flow_mount_new_device, flow_use_existing_mount) drive
questionary prompts and belong in e2e tests, not here.
"""

from __future__ import annotations

import pytest

from scripts.utils.storage_flows import parse_path_hints


class TestParsePathHints:
    def test_extracts_label_and_subdir(self):
        assert parse_path_hints("/mnt/minio/minio/data") == ("minio", "minio/data")

    def test_label_only_when_path_ends_at_mount(self):
        assert parse_path_hints("/mnt/usb") == ("usb", None)

    def test_non_mnt_path_returns_none_none(self):
        assert parse_path_hints("/srv/minio/data") == (None, None)

    def test_root_returns_none_none(self):
        assert parse_path_hints("/") == (None, None)

    def test_deep_subdir_preserved(self):
        label, subdir = parse_path_hints("/mnt/storage/minio/data/buckets")
        assert label == "storage"
        assert subdir == "minio/data/buckets"
