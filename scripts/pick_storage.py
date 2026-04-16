#!/usr/bin/env python3
"""
Connects to the remote host, lists safe external storage devices,
prompts the user to pick one, then runs the mount_storage playbook.

Run via: make mount
"""

import os

from rich.console import Console
from utils.ansible_utils import ANSIBLE_DIR, inventory_host_vars, make_connection, run_playbook
from utils.storage_flows import flow_mount_new_device

PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"

console = Console()


def main(host: str = "rpi") -> None:
    console.print("[bold]Fetching block devices from remote host...[/bold]")

    hvars = inventory_host_vars(host)
    conn = make_connection(hvars)

    result = flow_mount_new_device(conn)
    if not result:
        console.print("[yellow]No device mounted.[/yellow]")
        return

    device_path, label = result
    console.print(f"\n[bold green]Mounting {device_path} at /mnt/{label}...[/bold green]")
    run_playbook(PLAYBOOK, device=device_path, label=label)


if __name__ == "__main__":
    main(host=os.environ.get("HOST", "rpi"))
