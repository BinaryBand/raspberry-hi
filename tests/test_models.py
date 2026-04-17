"""Tests for Pydantic models — validation, defaults, and field constraints."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import BlockDevice, HostVars, MountInfo, VaultSecrets


class TestBlockDevice:
    """Test suite for BlockDevice model validation."""

    def test_requires_name(self):
        """Ensure validation fails when name is missing."""
        with pytest.raises(ValidationError):
            BlockDevice.model_validate({})

    def test_optional_fields_default_to_none(self):
        """Verify optional fields default to None."""
        bd = BlockDevice(name="sda")
        assert bd.type is None
        assert bd.fstype is None
        assert bd.children is None
        assert bd.mountpoint is None

    def test_recursive_children(self):
        """Verify recursive parsing of block device children."""
        bd = BlockDevice.model_validate(
            {
                "name": "sda",
                "type": "disk",
                "children": [{"name": "sda1", "type": "part", "fstype": "ext4"}],
            }
        )
        assert bd.children is not None
        assert bd.children[0].name == "sda1"
        assert isinstance(bd.children[0], BlockDevice)

    def test_extra_fields_allowed(self):
        """Ensure extra model fields are allowed and don't break construction."""
        bd = BlockDevice.model_validate({"name": "sda", "kname": "sda"})
        assert bd.name == "sda"


class TestMountInfo:
    """Test suite for MountInfo model validation."""

    def test_requires_target(self):
        """Ensure validation fails when target is missing."""
        with pytest.raises(ValidationError):
            MountInfo.model_validate({})

    def test_optional_fields_default_to_none(self):
        """Verify optional fields default to None."""
        m = MountInfo(target="/mnt/usb")
        assert m.source is None
        assert m.fstype is None
        assert m.size is None

    def test_extra_fields_allowed(self):
        """Ensure extra model fields are allowed."""
        m = MountInfo.model_validate({"target": "/mnt/usb", "options": "rw,nofail"})
        assert m.target == "/mnt/usb"


class TestHostVars:
    """Test suite for HostVars model validation."""

    def test_requires_ansible_host(self):
        """Ensure validation fails when ansible_host is missing."""
        with pytest.raises(ValidationError):
            HostVars.model_validate({})

    def test_optional_fields_default_to_none(self):
        """Verify optional fields default to None."""
        h = HostVars(ansible_host="192.168.0.33")
        assert h.ansible_user is None
        assert h.ansible_port is None
        assert h.ansible_ssh_private_key_file is None

    def test_full_construction(self):
        """Verify successful full model construction."""
        h = HostVars(
            ansible_host="192.168.0.33",
            ansible_user="pi",
            ansible_port=22,
            ansible_ssh_private_key_file="config/.ed25519",
        )
        assert h.ansible_host == "192.168.0.33"

    def test_extra_fields_allowed(self):
        """Ensure extra model fields are allowed."""
        h = HostVars.model_validate({"ansible_host": "192.168.0.33", "minio_data_path": "/mnt/usb"})
        assert h.ansible_host == "192.168.0.33"


class TestVaultSecrets:
    """Test suite for VaultSecrets model validation."""

    def test_all_fields_optional(self):
        """Ensure all fields are optional."""
        v = VaultSecrets()
        assert v.become_passwords is None

    def test_become_passwords_dict(self):
        """Verify become_passwords stores per-host passwords as a dict."""
        v = VaultSecrets(become_passwords={"rpi": "pass1", "debian": "pass2"})
        assert v.become_passwords == {"rpi": "pass1", "debian": "pass2"}

    def test_extra_fields_allowed(self):
        """Ensure app secrets stored in the vault are accessible as extra fields."""
        v = VaultSecrets.model_validate({"minio_root_user": "admin", "other_secret": "x"})
        assert v.model_extra["minio_root_user"] == "admin"
        assert v.model_extra["other_secret"] == "x"
