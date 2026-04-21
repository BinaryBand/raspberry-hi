from __future__ import annotations

from typing import Any

from models import ANSIBLE_DATA, AppRegistryEntry, HostVars
from utils.ansible_connection import make_connection
from utils.ansible_role_vars import role_required_vars

ROOT = ANSIBLE_DATA.root
ANSIBLE_DIR = ANSIBLE_DATA.ansible_dir
INVENTORY_DIR = ANSIBLE_DATA.inventory_dir


def load_app_registry() -> dict[str, AppRegistryEntry]:
    """Return the validated app registry keyed by app name."""
    return ANSIBLE_DATA.load_app_registry()


def all_apps() -> list[str]:
    """Return all registered app names in declared order."""
    return ANSIBLE_DATA.all_apps()


def containerized_apps() -> list[str]:
    """Return registered apps with a long-running container service."""
    return ANSIBLE_DATA.containerized_apps()


def restore_apps() -> list[str]:
    """Return registered apps that participate in restore flows."""
    return ANSIBLE_DATA.restore_apps()


def cleanup_apps() -> list[str]:
    """Return registered apps that participate in cleanup flows."""
    return ANSIBLE_DATA.cleanup_apps()


def get_app_entry(app: str) -> AppRegistryEntry:
    """Return a single validated registry entry."""
    return ANSIBLE_DATA.get_app_entry(app)


def read_host_vars_raw(hostname: str) -> dict[str, Any]:
    """Read host_vars data for a host from the Ansible inventory."""
    return ANSIBLE_DATA.read_host_vars_raw(hostname)


def write_host_vars_raw(hostname: str, updates: dict[str, Any]) -> None:
    """Merge and persist host_vars data for a host."""
    ANSIBLE_DATA.write_host_vars_raw(hostname, updates)


def inventory_host_vars(hostname: str) -> HostVars:
    """Return validated inventory host vars for a host alias."""
    return ANSIBLE_DATA.host_vars(hostname)


__all__ = [
    "ANSIBLE_DIR",
    "INVENTORY_DIR",
    "ROOT",
    "all_apps",
    "cleanup_apps",
    "containerized_apps",
    "get_app_entry",
    "inventory_host_vars",
    "load_app_registry",
    "make_connection",
    "read_host_vars_raw",
    "restore_apps",
    "role_required_vars",
    "write_host_vars_raw",
]
