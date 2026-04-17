"""Ansible inventory and connection helpers shared by local Python code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from utils.yaml_utils import yaml_mapping

if TYPE_CHECKING:
    from fabric import Connection

    from models import HostVars

# lib/ → scripts/ → project root
ROOT = Path(__file__).resolve().parent.parent.parent
ANSIBLE_DIR = ROOT / "ansible"


# ---------------------------------------------------------------------------
# Role introspection
# ---------------------------------------------------------------------------


def role_required_vars(role_path: Path) -> list[str]:
    """Return variable names whose default is null (~) in a role's defaults/main.yml.

    Null is the sentinel for "required — no default." Python reads this to know
    what to prompt for; Ansible asserts the same vars are not none at runtime.
    Neither side maintains its own list.
    """
    defaults_file = role_path / "defaults" / "main.yml"
    if not defaults_file.exists():
        return []
    data = yaml_mapping(yaml.safe_load(defaults_file.read_text()), source=defaults_file)
    return [k for k, v in data.items() if v is None]


def read_host_vars_raw(hostname: str) -> dict[str, Any]:
    """Return the raw host_vars dict for *hostname*, or {} if the file is missing."""
    path = ANSIBLE_DIR / "inventory" / "host_vars" / f"{hostname}.yml"
    if not path.exists():
        return {}
    return yaml_mapping(yaml.safe_load(path.read_text()), source=path)


def write_host_vars_raw(hostname: str, updates: dict[str, Any]) -> None:
    """Merge *updates* into host_vars/<hostname>.yml, preserving comments and formatting."""
    from ruamel.yaml import YAML

    path = ANSIBLE_DIR / "inventory" / "host_vars" / f"{hostname}.yml"
    ryaml = YAML()
    ryaml.preserve_quotes = True
    ryaml.width = 4096
    data = yaml_mapping(ryaml.load(path) if path.exists() else None, source=path)
    data.update(updates)
    ryaml.dump(data, path)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def inventory_host_vars(host: str = "rpi") -> HostVars:
    """Return merged host vars from ansible-inventory for *host*."""
    from models import HostVars

    from .exec_utils import run_resolved

    result = run_resolved(
        ["ansible-inventory", "--host", host],
        capture_output=True,
        text=True,
        cwd=str(ANSIBLE_DIR),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ansible-inventory failed: {result.stderr.strip()}")
    return HostVars.model_validate(json.loads(result.stdout))


# ---------------------------------------------------------------------------
# SSH connection
# ---------------------------------------------------------------------------


def make_connection(hvars: HostVars) -> Connection:
    """Return a Fabric Connection for *hvars*, resolving relative key paths."""
    from fabric import Connection

    connect_kwargs: dict[str, str] = {}
    if hvars.ansible_ssh_private_key_file:
        key_path = Path(hvars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ROOT / key_path
        connect_kwargs["key_filename"] = str(key_path)
    return Connection(
        host=hvars.ansible_host,
        user=hvars.ansible_user,
        port=hvars.ansible_port,
        connect_kwargs=connect_kwargs,
    )
