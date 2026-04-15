"""Tests for Pydantic models — validation, defaults, and field constraints."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import BlockDevice, HostVars, MinioConfig, MountInfo, VaultSecrets


class TestBlockDevice:
    def test_requires_name(self):
        with pytest.raises(ValidationError):
            BlockDevice.model_validate({})

    def test_optional_fields_default_to_none(self):
        bd = BlockDevice(name="sda")
        assert bd.type is None
        assert bd.fstype is None
        assert bd.children is None
        assert bd.mountpoint is None

    def test_recursive_children(self):
        bd = BlockDevice.model_validate({
            "name": "sda",
            "type": "disk",
            "children": [{"name": "sda1", "type": "part", "fstype": "ext4"}],
        })
        assert bd.children is not None
        assert bd.children[0].name == "sda1"
        assert isinstance(bd.children[0], BlockDevice)

    def test_extra_fields_allowed(self):
        bd = BlockDevice.model_validate({"name": "sda", "kname": "sda"})
        assert bd.name == "sda"


class TestMountInfo:
    def test_requires_target(self):
        with pytest.raises(ValidationError):
            MountInfo.model_validate({})

    def test_optional_fields_default_to_none(self):
        m = MountInfo(target="/mnt/usb")
        assert m.source is None
        assert m.fstype is None
        assert m.size is None

    def test_extra_fields_allowed(self):
        m = MountInfo.model_validate({"target": "/mnt/usb", "options": "rw,nofail"})
        assert m.target == "/mnt/usb"


class TestMinioConfig:
    def test_default_data_path(self):
        assert MinioConfig().minio_data_path == "/srv/minio/data"

    def test_default_requires_external_mount(self):
        assert MinioConfig().minio_require_external_mount is True

    def test_host_var_overrides_default(self):
        cfg = MinioConfig(minio_data_path="/mnt/usb/minio/data")
        assert cfg.minio_data_path == "/mnt/usb/minio/data"

    def test_model_validate_merges_role_defaults_and_host_vars(self):
        role_defaults = {"minio_data_path": "/srv/minio/data", "minio_require_external_mount": True}
        host_vars = {"minio_data_path": "/mnt/usb/minio/data"}
        cfg = MinioConfig.model_validate({**role_defaults, **host_vars})
        assert cfg.minio_data_path == "/mnt/usb/minio/data"
        assert cfg.minio_require_external_mount is True

    def test_extra_fields_allowed(self):
        cfg = MinioConfig.model_validate({"brew_user": "pi"})
        assert cfg.minio_data_path == "/srv/minio/data"


class TestHostVars:
    def test_requires_ansible_host(self):
        with pytest.raises(ValidationError):
            HostVars.model_validate({})

    def test_optional_fields_default_to_none(self):
        h = HostVars(ansible_host="192.168.0.33")
        assert h.ansible_user is None
        assert h.ansible_port is None
        assert h.ansible_ssh_private_key_file is None

    def test_full_construction(self):
        h = HostVars(
            ansible_host="192.168.0.33",
            ansible_user="pi",
            ansible_port=22,
            ansible_ssh_private_key_file="config/.ed25519",
        )
        assert h.ansible_host == "192.168.0.33"

    def test_extra_fields_allowed(self):
        h = HostVars.model_validate({"ansible_host": "192.168.0.33", "minio_data_path": "/mnt/usb"})
        assert h.ansible_host == "192.168.0.33"


class TestVaultSecrets:
    def test_all_fields_optional(self):
        v = VaultSecrets()
        assert v.minio_root_user is None
        assert v.minio_root_password is None

    def test_construction_with_values(self):
        v = VaultSecrets(minio_root_user="admin", minio_root_password="secret")
        assert v.minio_root_user == "admin"

    def test_extra_fields_allowed(self):
        v = VaultSecrets.model_validate({"minio_root_user": "admin", "other_secret": "x"})
        assert v.minio_root_user == "admin"
