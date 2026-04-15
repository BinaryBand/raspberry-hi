"""Tests for ansible_utils file-I/O helpers — no subprocess, no network.

ANSIBLE_DIR is redirected to tmp_path via monkeypatch so tests never
touch the real inventory or role files.
"""

from __future__ import annotations

import pytest
import yaml

import scripts.utils.ansible_utils as ansible_utils
from scripts.utils.ansible_utils import (
    read_host_vars,
    read_role_defaults,
    update_host_vars,
    write_host_vars,
)


@pytest.fixture
def ansible_dir(tmp_path, monkeypatch):
    """Redirect ANSIBLE_DIR to a blank temp tree and return its path."""
    monkeypatch.setattr(ansible_utils, "ANSIBLE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def host_vars_dir(ansible_dir):
    """Create the inventory/host_vars directory and return it."""
    d = ansible_dir / "inventory" / "host_vars"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------------------
# read_host_vars
# ---------------------------------------------------------------------------


class TestReadHostVars:
    def test_returns_empty_when_file_missing(self, ansible_dir):
        assert read_host_vars("nonexistent") == {}

    def test_parses_existing_file(self, host_vars_dir):
        (host_vars_dir / "rpi.yml").write_text("ansible_user: pi\nansible_host: 192.168.0.33\n")
        result = read_host_vars("rpi")
        assert result["ansible_user"] == "pi"
        assert result["ansible_host"] == "192.168.0.33"

    def test_returns_empty_for_blank_file(self, host_vars_dir):
        (host_vars_dir / "rpi.yml").write_text("")
        assert read_host_vars("rpi") == {}


# ---------------------------------------------------------------------------
# write_host_vars
# ---------------------------------------------------------------------------


class TestWriteHostVars:
    def test_creates_file_with_yaml_header(self, host_vars_dir):
        write_host_vars("rpi", {"ansible_user": "pi"})
        content = (host_vars_dir / "rpi.yml").read_text()
        assert content.startswith("---\n")

    def test_round_trip(self, host_vars_dir):
        data = {"ansible_user": "pi", "ansible_host": "192.168.0.33", "ansible_port": 22}
        write_host_vars("rpi", data)
        assert read_host_vars("rpi") == data

    def test_overwrites_existing_file(self, host_vars_dir):
        (host_vars_dir / "rpi.yml").write_text("ansible_user: old\n")
        write_host_vars("rpi", {"ansible_user": "new"})
        assert read_host_vars("rpi")["ansible_user"] == "new"


# ---------------------------------------------------------------------------
# update_host_vars
# ---------------------------------------------------------------------------


class TestUpdateHostVars:
    def test_adds_new_key(self, host_vars_dir):
        (host_vars_dir / "rpi.yml").write_text("ansible_user: pi\n")
        update_host_vars("rpi", minio_data_path="/mnt/usb/minio")
        result = read_host_vars("rpi")
        assert result["minio_data_path"] == "/mnt/usb/minio"

    def test_preserves_existing_keys(self, host_vars_dir):
        (host_vars_dir / "rpi.yml").write_text("ansible_user: pi\n")
        update_host_vars("rpi", minio_data_path="/mnt/usb/minio")
        assert read_host_vars("rpi")["ansible_user"] == "pi"

    def test_overwrites_existing_key(self, host_vars_dir):
        (host_vars_dir / "rpi.yml").write_text("minio_data_path: /old/path\n")
        update_host_vars("rpi", minio_data_path="/new/path")
        assert read_host_vars("rpi")["minio_data_path"] == "/new/path"

    def test_creates_file_when_missing(self, ansible_dir, host_vars_dir):
        update_host_vars("newhost", minio_data_path="/mnt/usb")
        assert read_host_vars("newhost")["minio_data_path"] == "/mnt/usb"


# ---------------------------------------------------------------------------
# read_role_defaults
# ---------------------------------------------------------------------------


class TestReadRoleDefaults:
    def test_finds_role_in_roles_dir(self, ansible_dir):
        d = ansible_dir / "roles" / "storage" / "defaults"
        d.mkdir(parents=True)
        (d / "main.yml").write_text("minio_require_external_mount: true\n")
        assert read_role_defaults("storage") == {"minio_require_external_mount": True}

    def test_finds_role_in_apps_dir(self, ansible_dir):
        d = ansible_dir / "apps" / "minio" / "defaults"
        d.mkdir(parents=True)
        (d / "main.yml").write_text("minio_data_path: /srv/minio/data\n")
        assert read_role_defaults("minio") == {"minio_data_path": "/srv/minio/data"}

    def test_returns_empty_when_role_not_found(self, ansible_dir):
        assert read_role_defaults("nonexistent") == {}

    def test_returns_empty_for_blank_defaults(self, ansible_dir):
        d = ansible_dir / "roles" / "empty" / "defaults"
        d.mkdir(parents=True)
        (d / "main.yml").write_text("")
        assert read_role_defaults("empty") == {}
