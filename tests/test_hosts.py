"""Tests for the host management CLI and inventory helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from linux_hi.cli.hosts import cmd_list
from models import ANSIBLE_DATA
from models.ansible.access import AnsibleDataStore


def test_hosts_list_covers_all_inventory_hosts(capsys: pytest.CaptureFixture[str]) -> None:
    """hosts-list must display every host in the configured inventory."""
    cmd_list(argparse.Namespace())
    captured = capsys.readouterr()
    for alias in ANSIBLE_DATA.inventory_hosts():
        assert alias in captured.out, f"Expected '{alias}' in hosts-list output"


_MINIMAL_INVENTORY = "all:\n  children:\n    devices:\n      hosts:\n        rpi:\n"


def _temp_store(tmp_path: Path, content: str = _MINIMAL_INVENTORY) -> AnsibleDataStore:
    inv = tmp_path / "inventory" / "hosts.yml"
    inv.parent.mkdir(parents=True, exist_ok=True)
    inv.write_text(content, encoding="utf-8")
    return AnsibleDataStore.from_inventory_file(inv)


def test_add_inventory_host_appears_in_hosts(tmp_path: Path) -> None:
    """add_inventory_host must persist the new alias so inventory_hosts reflects it."""
    store = _temp_store(tmp_path)
    store.add_inventory_host("newhost")
    assert "newhost" in store.inventory_hosts()


def test_add_inventory_host_rejects_duplicate(tmp_path: Path) -> None:
    """Adding an alias that already exists must raise ValueError."""
    store = _temp_store(tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        store.add_inventory_host("rpi")


def test_remove_inventory_host_no_longer_in_hosts(tmp_path: Path) -> None:
    """remove_inventory_host must drop the alias while leaving others intact."""
    content = "all:\n  children:\n    devices:\n      hosts:\n        rpi:\n        rpi2:\n"
    store = _temp_store(tmp_path, content)
    store.remove_inventory_host("rpi")
    assert "rpi" not in store.inventory_hosts()
    assert "rpi2" in store.inventory_hosts()


def test_remove_inventory_host_rejects_unknown(tmp_path: Path) -> None:
    """Removing a host not in inventory must raise KeyError."""
    store = _temp_store(tmp_path)
    with pytest.raises(KeyError):
        store.remove_inventory_host("ghost")


def test_remove_host_vars_deletes_file(tmp_path: Path) -> None:
    """remove_host_vars must delete the host_vars file when it exists."""
    store = _temp_store(tmp_path)
    hv_file = store.host_vars_dir / "rpi.yml"
    hv_file.parent.mkdir(parents=True, exist_ok=True)
    hv_file.write_text("ansible_host: rpi.local\n", encoding="utf-8")
    store.remove_host_vars("rpi")
    assert not hv_file.exists()


def test_remove_host_vars_is_silent_when_missing(tmp_path: Path) -> None:
    """remove_host_vars must not raise when host_vars file does not exist."""
    store = _temp_store(tmp_path)
    store.remove_host_vars("rpi")  # no file created — must not raise


def test_hosts_list_shows_connection_details(capsys: pytest.CaptureFixture[str]) -> None:
    """hosts-list must show ansible_host for at least one host."""
    cmd_list(argparse.Namespace())
    captured = capsys.readouterr()
    hosts_with_explicit_host = [
        alias
        for alias in ANSIBLE_DATA.inventory_hosts()
        if ANSIBLE_DATA.host_vars(alias).ansible_host != alias
    ]
    for alias in hosts_with_explicit_host:
        hv = ANSIBLE_DATA.host_vars(alias)
        assert hv.ansible_host in captured.out, (
            f"Expected ansible_host '{hv.ansible_host}' for '{alias}' in hosts-list output"
        )
