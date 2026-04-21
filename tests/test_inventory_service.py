"""Tests for inventory helpers backed by the actual Ansible inventory parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.ansible.inventory import discover_hosts, require_inventory_host


def test_discover_hosts_uses_inventory_aliases() -> None:
    """The helper should return the tracked host aliases from inventory."""
    assert discover_hosts() == ["debian", "rpi", "rpi2"]


def test_discover_hosts_from_temp_inventory(tmp_path: Path) -> None:
    """Custom inventory paths should still be parsed via Ansible's inventory engine."""
    inventory_dir = tmp_path / "inventory"
    inventory_dir.mkdir()
    inventory_file = inventory_dir / "hosts.ini"
    inventory_file.write_text("[devices]\nalpha\nbeta\n", encoding="utf-8")

    assert discover_hosts(inventory_file) == ["alpha", "beta"]


def test_require_inventory_host_rejects_unknown_host() -> None:
    """Unknown inventory aliases should raise a clear error."""
    with pytest.raises(KeyError, match="Unknown inventory host"):
        require_inventory_host("missing")
