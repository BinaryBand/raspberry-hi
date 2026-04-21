from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString
from utils.yaml_utils import yaml_mapping

from .hostvars import HostVars
from .registry import AppRegistry, AppRegistryEntry


class AnsibleDataStore:
    """Central access point for validated Ansible project data."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]
        self.ansible_dir = self.root / "ansible"
        self.inventory_dir = self.ansible_dir / "inventory"
        self.host_vars_dir = self.inventory_dir / "host_vars"
        self.registry_file = self.ansible_dir / "registry.yml"
        self._app_registry_cache: dict[str, AppRegistryEntry] | None = None

    def clear_cache(self) -> None:
        """Drop any cached registry data."""
        self._app_registry_cache = None

    def load_app_registry(self) -> dict[str, AppRegistryEntry]:
        """Return the validated app registry keyed by app name."""
        if self._app_registry_cache is None:
            data = self._read_yaml_mapping(self.registry_file)
            self._app_registry_cache = AppRegistry.model_validate(data).apps
        return self._app_registry_cache

    def all_apps(self) -> list[str]:
        """Return all registered app names in declared order."""
        return list(self.load_app_registry().keys())

    def containerized_apps(self) -> list[str]:
        """Return apps with a long-running container service."""
        registry = self.load_app_registry()
        return [name for name, entry in registry.items() if entry.service_type == "containerized"]

    def restore_apps(self) -> list[str]:
        """Return apps that participate in restore flows."""
        registry = self.load_app_registry()
        return [name for name, entry in registry.items() if entry.restore]

    def cleanup_apps(self) -> list[str]:
        """Return apps that participate in cleanup flows."""
        registry = self.load_app_registry()
        return [name for name, entry in registry.items() if entry.cleanup]

    def get_app_entry(self, app: str) -> AppRegistryEntry:
        """Return a single validated app registry entry."""
        return self.load_app_registry()[app]

    def host_vars_path(self, hostname: str) -> Path:
        """Return the inventory path for a host's host_vars file."""
        return self.host_vars_dir / f"{hostname}.yml"

    def read_host_vars_raw(self, hostname: str) -> dict[str, Any]:
        """Read host_vars data for a host from the Ansible inventory."""
        host_vars_file = self.host_vars_path(hostname)
        if not host_vars_file.exists():
            return {}
        return self._read_yaml_mapping(host_vars_file)

    def write_host_vars_raw(self, hostname: str, updates: dict[str, Any]) -> None:
        """Merge and persist host_vars data for a host."""
        host_vars_file = self.host_vars_path(hostname)
        current = self.read_host_vars_raw(hostname)
        current.update(updates)
        host_vars_file.parent.mkdir(parents=True, exist_ok=True)

        yaml_round_trip = YAML()
        yaml_round_trip.preserve_quotes = True

        if "ansible_become_password" in current:
            value = current["ansible_become_password"]
            if not isinstance(value, DoubleQuotedScalarString):
                current["ansible_become_password"] = DoubleQuotedScalarString(str(value))

        with host_vars_file.open("w", encoding="utf-8") as handle:
            yaml_round_trip.dump(current, handle)

    def host_vars(self, hostname: str) -> HostVars:
        """Return validated inventory host vars for a host alias."""
        return HostVars.from_inventory(hostname, self.read_host_vars_raw(hostname))

    def _read_yaml_mapping(self, source: Path) -> dict[str, Any]:
        """Load a YAML mapping from disk and type it at the boundary."""
        return yaml_mapping(yaml.safe_load(source.read_text(encoding="utf-8")), source=source)


ANSIBLE_DATA = AnsibleDataStore()
