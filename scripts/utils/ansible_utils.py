from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fabric import Config, Connection

from models import ANSIBLE_DATA, AppRegistryEntry, HostVars
from utils.yaml_utils import yaml_mapping

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


def role_required_vars(role_path: Path) -> list[str]:
    """Return names whose defaults/main.yml values are explicitly null."""
    defaults_file = role_path / "defaults" / "main.yml"
    if not defaults_file.exists():
        return []

    data = yaml_mapping(yaml.safe_load(defaults_file.read_text()), source=defaults_file)
    return [name for name, value in data.items() if value is None]


def read_host_vars_raw(hostname: str) -> dict[str, Any]:
    """Read host_vars data for a host from the Ansible inventory."""
    return ANSIBLE_DATA.read_host_vars_raw(hostname)


def write_host_vars_raw(hostname: str, updates: dict[str, Any]) -> None:
    """Merge and persist host_vars data for a host."""
    ANSIBLE_DATA.write_host_vars_raw(hostname, updates)


def inventory_host_vars(hostname: str) -> HostVars:
    """Return validated inventory host vars for a host alias."""
    return ANSIBLE_DATA.host_vars(hostname)


def make_connection(host: str | HostVars, *, become_password: str | None = None) -> Connection:
    """Create a Fabric connection from a host alias or validated HostVars."""
    host_vars = ANSIBLE_DATA.host_vars(host) if isinstance(host, str) else host

    connect_kwargs: dict[str, str] = {}
    if host_vars.ansible_ssh_private_key_file:
        key_path = Path(host_vars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ANSIBLE_DATA.root / key_path
        connect_kwargs["key_filename"] = str(key_path)

    config = (
        Config(overrides={"sudo": {"password": become_password}})
        if become_password is not None
        else None
    )

    return Connection(
        host=host_vars.ansible_host,
        user=host_vars.ansible_user,
        port=host_vars.ansible_port or 22,
        connect_kwargs=connect_kwargs,
        config=config,
    )
