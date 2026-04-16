"""Tests for the MinIO preflight Ansible module's file update helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


def load_minio_preflight_module():
    """Load the standalone Ansible module so its helper can be unit-tested."""
    module_path = Path(__file__).resolve().parents[1] / "ansible" / "library" / "minio_preflight.py"
    spec = importlib.util.spec_from_file_location("minio_preflight", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestUpdateHostVars:
    """Test suite for persisting MinIO data path updates back to host_vars."""

    def test_creates_file_with_yaml_header(self, tmp_path):
        """Verify the helper creates a valid YAML file with the standard header."""
        module = load_minio_preflight_module()
        target = tmp_path / "rpi.yml"

        module.update_host_vars(target, "/mnt/minio/data")

        assert target.read_text().startswith("---\n")

    def test_preserves_existing_fields(self, tmp_path):
        """Verify existing host vars survive when only minio_data_path changes."""
        module = load_minio_preflight_module()
        target = tmp_path / "rpi.yml"
        target.write_text(
            "---\nansible_host: rpi.local\nansible_user: pi\nminio_require_external_mount: true\n"
        )

        module.update_host_vars(target, "/mnt/storage/minio/data")

        data = yaml.safe_load(target.read_text())
        assert data == {
            "ansible_host": "rpi.local",
            "ansible_user": "pi",
            "minio_require_external_mount": True,
            "minio_data_path": "/mnt/storage/minio/data",
        }

    def test_overwrites_existing_path(self, tmp_path):
        """Verify an existing MinIO path is replaced with the selected mount path."""
        module = load_minio_preflight_module()
        target = tmp_path / "rpi.yml"
        target.write_text("---\nminio_data_path: /srv/minio/data\n")

        module.update_host_vars(target, "/mnt/usb/minio/data")

        data = yaml.safe_load(target.read_text())
        assert data["minio_data_path"] == "/mnt/usb/minio/data"
