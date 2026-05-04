"""Tests for shared Ansible utility helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from linux_hi.models import ANSIBLE_DATA, HostVars
from linux_hi.models.ansible import access as ansible_access
from linux_hi.models.ansible import connection as ansible_connection
from tests.support.connections import RecordingConnectionFactory


def _temp_store_with_host(tmp_path: Path, alias: str = "alpha") -> ansible_access.AnsibleDataStore:
    """Build an isolated AnsibleDataStore bound to a temporary inventory."""
    inventory_dir = tmp_path / "inventory"
    inventory_dir.mkdir(parents=True, exist_ok=True)
    inventory_file = inventory_dir / "hosts.yml"
    inventory_file.write_text(
        f"all:\n  children:\n    devices:\n      hosts:\n        {alias}:\n",
        encoding="utf-8",
    )
    return ansible_access.AnsibleDataStore.from_inventory_file(inventory_file)


def _capture_connection_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Patch Connection with a recording test double and return captured kwargs."""
    captured: dict[str, Any] = {}

    class CapturingConnectionFactory(RecordingConnectionFactory):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            captured.update(kwargs)

    monkeypatch.setattr(ansible_connection, "Connection", CapturingConnectionFactory)
    return captured


def test_make_connection_uses_relative_ssh_key_from_repo_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative SSH key paths should be resolved against the repository root."""
    captured = _capture_connection_kwargs(monkeypatch)

    host = HostVars(
        ansible_host="example.local",
        ansible_user="owen",
        ansible_port=2202,
        ansible_ssh_private_key_file="config/.id_ed25519",
    )

    ansible_connection.make_connection(host)

    assert captured["host"] == "example.local"
    assert captured["user"] == "owen"
    assert captured["port"] == 2202
    assert captured["connect_kwargs"]["key_filename"] == str(
        ANSIBLE_DATA.root / "config/.id_ed25519"
    )
    assert captured["config"] is None


def test_make_connection_can_configure_sudo_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sudo password should be forwarded into Fabric config when requested."""
    captured = _capture_connection_kwargs(monkeypatch)

    host = HostVars(ansible_host="example.local", ansible_user="owen")
    sudo_value = "mount-sudo-value"
    ansible_connection.make_connection(host, become_password=sudo_value)

    assert captured["config"] is not None
    assert captured["config"].sudo.password == sudo_value


def test_load_app_registry_is_cached(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repeated registry reads in one process should hit the parser only once."""
    registry_file: Path = tmp_path / "registry.yml"
    registry_file.write_text(
        """
apps:
  minio:
    service_type: containerized
    service_name: minio
    dependencies: []
    preflight_vars: {}
    vault_secrets: []
""".lstrip(),
        encoding="utf-8",
    )

    original_safe_load: Callable[..., Any] = yaml.safe_load
    calls = 0

    def counting_safe_load(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original_safe_load(*args, **kwargs)

    monkeypatch.setattr(ANSIBLE_DATA, "registry_file", registry_file)
    monkeypatch.setattr(ansible_access.yaml, "safe_load", counting_safe_load)
    ANSIBLE_DATA.clear_cache()

    assert list(ANSIBLE_DATA.load_app_registry().keys()) == ["minio"]
    assert list(ANSIBLE_DATA.load_app_registry().keys()) == ["minio"]
    assert calls == 1

    ANSIBLE_DATA.clear_cache()


def test_inventory_host_vars_falls_back_to_hostname_for_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing host_vars should still produce a valid HostVars object."""
    alias = "alpha"
    store = _temp_store_with_host(tmp_path, alias=alias)
    monkeypatch.setattr(store, "host_vars_dir", tmp_path / "missing-host-vars")

    host = store.host_vars(alias)

    assert host.ansible_host == alias


def test_inventory_host_vars_rejects_unknown_inventory_alias() -> None:
    """Unknown inventory aliases should fail before fabric connection setup."""
    with pytest.raises(KeyError, match="Unknown inventory host"):
        ANSIBLE_DATA.host_vars("unknown-host")


def test_read_effective_vars_merges_group_vars_under_host_vars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """host_vars should override group_vars; group_vars fill in the rest."""
    group_vars_dir = tmp_path / "group_vars" / "all"
    group_vars_dir.mkdir(parents=True)
    (group_vars_dir / "vars.yml").write_text(
        "shared_var: from_group\ngroup_only_var: group_value\n", encoding="utf-8"
    )

    host_vars_dir = tmp_path / "host_vars"
    host_vars_dir.mkdir()
    alias = "alpha"
    (host_vars_dir / f"{alias}.yml").write_text(
        "shared_var: from_host\nhost_only_var: host_value\n", encoding="utf-8"
    )

    store = _temp_store_with_host(tmp_path, alias=alias)
    monkeypatch.setattr(store, "ansible_dir", tmp_path)
    monkeypatch.setattr(store, "host_vars_dir", host_vars_dir)

    result = store.read_effective_vars(alias)

    assert result["group_only_var"] == "group_value"
    assert result["host_only_var"] == "host_value"
    assert result["shared_var"] == "from_host"
