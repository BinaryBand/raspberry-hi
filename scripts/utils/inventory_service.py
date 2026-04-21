from __future__ import annotations

from pathlib import Path

from models import ANSIBLE_DATA

INVENTORY_FILE = ANSIBLE_DATA.inventory_file


def discover_hosts(inventory_file: Path = INVENTORY_FILE) -> list[str]:
    """Return host aliases from the actual Ansible inventory."""
    if inventory_file != ANSIBLE_DATA.inventory_file:
        isolated_store = type(ANSIBLE_DATA)(root=inventory_file.parents[2])
        isolated_store.inventory_file = inventory_file
        isolated_store.inventory_dir = inventory_file.parent
        isolated_store.host_vars_dir = inventory_file.parent / "host_vars"
        return isolated_store.inventory_hosts()
    return ANSIBLE_DATA.inventory_hosts()


def require_inventory_host(hostname: str) -> str:
    """Validate that *hostname* exists in inventory and return it unchanged."""
    return ANSIBLE_DATA.require_inventory_host(hostname)
