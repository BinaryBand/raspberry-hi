"""Tests for inventory helpers backed by the actual Ansible inventory parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.models import ANSIBLE_DATA
from linux_hi.models.ansible.access import AnsibleDataStore


def test_inventory_hosts_returns_configured_aliases() -> None:
    """inventory_hosts() should return the tracked host aliases from inventory."""
    assert ANSIBLE_DATA.inventory_hosts() == ["debian", "rpi", "rpi2"]


def test_inventory_hosts_from_temp_inventory(tmp_path: Path) -> None:
    """Custom inventory paths should still be parsed via Ansible's inventory engine."""
    inventory_dir = tmp_path / "inventory"
    inventory_dir.mkdir()
    inventory_file = inventory_dir / "hosts.yml"
    inventory_file.write_text(
        "all:\n  children:\n    devices:\n      hosts:\n        alpha:\n        beta:\n",
        encoding="utf-8",
    )
    store = AnsibleDataStore.from_inventory_file(inventory_file)
    assert store.inventory_hosts() == ["alpha", "beta"]


def test_require_inventory_host_rejects_unknown_host() -> None:
    """Unknown inventory aliases should raise a clear error."""
    with pytest.raises(KeyError, match="Unknown inventory host"):
        ANSIBLE_DATA.require_inventory_host("missing")
