"""Ansible inventory, playbook, and host-vars helpers.

All scripts share these primitives rather than duplicating them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from fabric import Connection
    from models import HostVars

# lib/ → scripts/ → project root
ROOT = Path(__file__).resolve().parent.parent.parent
ANSIBLE_DIR = ROOT / "ansible"


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def inventory_host_vars(host: str = "rpi") -> HostVars:
    """Return merged host vars from ansible-inventory for *host*."""
    from .exec_utils import run_resolved
    from models import HostVars

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

    connect_kwargs: dict = {}
    if hvars.ansible_ssh_private_key_file:
        key_path = Path(hvars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ROOT / key_path
        connect_kwargs["key_filename"] = str(key_path)
    return Connection(host=hvars.ansible_host, user=hvars.ansible_user, connect_kwargs=connect_kwargs)


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


def run_playbook(playbook: Path, **extra_vars: str) -> None:
    """Run *playbook* with optional extra vars, always from the project root.

    Running from ROOT ensures that relative paths in host_vars (e.g.
    ansible_ssh_private_key_file) resolve correctly against the project root
    rather than the ansible/ subdirectory.
    """
    from .exec_utils import run_resolved

    cmd = ["ansible-playbook", str(playbook)]
    for key, value in extra_vars.items():
        cmd += ["-e", f"{key}={value}"]

    run_resolved(
        cmd,
        cwd=str(ROOT),
        env={**os.environ, "ANSIBLE_CONFIG": str(ANSIBLE_DIR / "ansible.cfg")},
        check=True,
    )


# ---------------------------------------------------------------------------
# Role defaults
# ---------------------------------------------------------------------------


def read_role_defaults(role: str) -> dict:
    """Return the parsed defaults/main.yml for *role*."""
    path = ANSIBLE_DIR / "roles" / role / "defaults" / "main.yml"
    return yaml.safe_load(path.read_text()) or {}


# ---------------------------------------------------------------------------
# Host vars file (inventory/host_vars/<host>.yml)
# ---------------------------------------------------------------------------


def _host_vars_path(host: str) -> Path:
    return ANSIBLE_DIR / "inventory" / "host_vars" / f"{host}.yml"


def read_host_vars(host: str = "rpi") -> dict:
    """Read the raw YAML host_vars file for *host* as a plain dict."""
    path = _host_vars_path(host)
    return yaml.safe_load(path.read_text()) or {} if path.exists() else {}


def write_host_vars(host: str, data: dict) -> None:
    """Overwrite the host_vars file for *host* with *data*."""
    path = _host_vars_path(host)
    path.write_text("---\n" + yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False))


def update_host_vars(host: str, **kwargs) -> None:
    """Merge *kwargs* into the host_vars file for *host*."""
    data = read_host_vars(host)
    data.update(kwargs)
    write_host_vars(host, data)
