"""Tests for the MinIO preflight Ansible module's file update helper."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# ansible/library/ is not a Python package, so add it to sys.path.
# The module's own sys.path guard then wires up the project imports.
_LIB = str(Path(__file__).resolve().parent.parent / "ansible" / "library")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from minio_preflight import update_host_vars  # noqa: E402


class TestUpdateHostVars:
    """Test suite for persisting MinIO data path updates back to host_vars."""

    def test_creates_file_with_yaml_header(self, tmp_path):
        """Verify the helper creates a valid YAML file with the standard header."""
        target = tmp_path / "rpi.yml"

        update_host_vars(target, "/mnt/minio/data")

        assert target.read_text().startswith("---\n")

    def test_preserves_existing_fields(self, tmp_path):
        """Verify existing host vars survive when only minio_data_path changes."""
        target = tmp_path / "rpi.yml"
        target.write_text(
            "---\nansible_host: rpi.local\nansible_user: pi\nminio_require_external_mount: true\n"
        )

        update_host_vars(target, "/mnt/storage/minio/data")

        data = yaml.safe_load(target.read_text())
        assert data == {
            "ansible_host": "rpi.local",
            "ansible_user": "pi",
            "minio_require_external_mount": True,
            "minio_data_path": "/mnt/storage/minio/data",
        }

    def test_overwrites_existing_path(self, tmp_path):
        """Verify an existing MinIO path is replaced with the selected mount path."""
        target = tmp_path / "rpi.yml"
        target.write_text("---\nminio_data_path: /srv/minio/data\n")

        update_host_vars(target, "/mnt/usb/minio/data")

        data = yaml.safe_load(target.read_text())
        assert data["minio_data_path"] == "/mnt/usb/minio/data"
