from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fabric import Connection
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from models import AppRegistry, AppRegistryEntry, HostVars
from utils.yaml_utils import yaml_mapping

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "ansible"
INVENTORY_DIR = ANSIBLE_DIR / "inventory"
HOST_VARS_DIR = INVENTORY_DIR / "host_vars"
REGISTRY_FILE = ANSIBLE_DIR / "registry.yml"


def load_app_registry() -> dict[str, AppRegistryEntry]:
    """Return the validated app registry keyed by app name."""
    data = yaml_mapping(yaml.safe_load(REGISTRY_FILE.read_text()), source=REGISTRY_FILE)
    return AppRegistry.model_validate(data).apps


def all_apps() -> list[str]:
    """Return all registered app names in declared order."""
    return list(load_app_registry().keys())


def containerized_apps() -> list[str]:
    """Return registered apps with a long-running container service."""
    registry = load_app_registry()
    return [name for name, entry in registry.items() if entry.service_type == "containerized"]


def restore_apps() -> list[str]:
    """Return registered apps that participate in restore flows."""
    registry = load_app_registry()
    return [name for name, entry in registry.items() if entry.restore]


def cleanup_apps() -> list[str]:
    """Return registered apps that participate in cleanup flows."""
    registry = load_app_registry()
    return [name for name, entry in registry.items() if entry.cleanup]


def get_app_entry(app: str) -> AppRegistryEntry:
    """Return a single validated registry entry."""
    return load_app_registry()[app]


def role_required_vars(role_path: Path) -> list[str]:
    """Return names whose defaults/main.yml values are explicitly null."""
    defaults_file = role_path / "defaults" / "main.yml"
    if not defaults_file.exists():
        return []

    data = yaml_mapping(yaml.safe_load(defaults_file.read_text()), source=defaults_file)
    return [name for name, value in data.items() if value is None]


def read_host_vars_raw(hostname: str) -> dict[str, Any]:
    """Read host_vars data for a host from the Ansible inventory."""
    host_vars_file = HOST_VARS_DIR / f"{hostname}.yml"
    if not host_vars_file.exists():
        return {}
    return yaml_mapping(yaml.safe_load(host_vars_file.read_text()), source=host_vars_file)


def write_host_vars_raw(hostname: str, updates: dict[str, Any]) -> None:
    """Merge and persist host_vars data for a host."""
    host_vars_file = HOST_VARS_DIR / f"{hostname}.yml"
    current = read_host_vars_raw(hostname)
    current.update(updates)

    yaml_round_trip = YAML()
    yaml_round_trip.preserve_quotes = True

    if "ansible_become_password" in current:
        value = current["ansible_become_password"]
        if not isinstance(value, DoubleQuotedScalarString):
            current["ansible_become_password"] = DoubleQuotedScalarString(str(value))

    with host_vars_file.open("w", encoding="utf-8") as handle:
        yaml_round_trip.dump(current, handle)


def inventory_host_vars(hostname: str) -> HostVars:
    """Return validated inventory host vars for a host alias."""
    raw = read_host_vars_raw(hostname)
    if not raw:
        return HostVars(ansible_host=hostname)
    return HostVars.model_validate(raw)


def make_connection(host: str | HostVars) -> Connection:
    """Create a Fabric connection from a host alias or validated HostVars."""
    host_vars = inventory_host_vars(host) if isinstance(host, str) else host

    connect_kwargs: dict[str, str] = {}
    if host_vars.ansible_ssh_private_key_file:
        key_path = Path(host_vars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ROOT / key_path
        connect_kwargs["key_filename"] = str(key_path)

    return Connection(
        host=host_vars.ansible_host,
        user=host_vars.ansible_user,
        port=host_vars.ansible_port or 22,
        connect_kwargs=connect_kwargs,
    )
