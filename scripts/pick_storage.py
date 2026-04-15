#!/usr/bin/env python3
"""
Connects to the Raspberry Pi, lists safe external storage devices,
prompts the user to pick one, then runs the mount_storage playbook.

Run via: make mount
"""

import os
import sys
from pathlib import Path

from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from utils.ansible_utils import (  # noqa: E402
    ANSIBLE_DIR,
    inventory_host_vars,
    make_connection,
    run_playbook,
)
from utils.storage_flows import flow_mount_new_device  # noqa: E402

PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"

console = Console()


def main(host: str = "rpi") -> None:
    console.print("[bold]Fetching block devices from Raspberry Pi...[/bold]")

    hvars = inventory_host_vars(host)
    conn = make_connection(hvars)

    result = flow_mount_new_device(conn, run_playbook, PLAYBOOK)
    if not result:
        console.print("[yellow]No device mounted.[/yellow]")


if __name__ == "__main__":
    main(host=os.environ.get("HOST", "rpi"))
