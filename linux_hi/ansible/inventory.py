"""Inventory discovery helpers."""

from pathlib import Path

from models import ANSIBLE_DATA
from models.ansible import AnsibleDataStore

INVENTORY_FILE = ANSIBLE_DATA.inventory_file


def discover_hosts(inventory_file: Path = INVENTORY_FILE) -> list[str]:
    """Return host aliases from the actual Ansible inventory."""
    if inventory_file != ANSIBLE_DATA.inventory_file:
        isolated_store = AnsibleDataStore.from_inventory_file(inventory_file)
        return isolated_store.inventory_hosts()
    return ANSIBLE_DATA.inventory_hosts()


__all__ = ["discover_hosts"]
