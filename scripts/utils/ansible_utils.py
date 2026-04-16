"""Ansible inventory and connection helpers shared by local Python code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

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

    connect_kwargs: dict = {}
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
