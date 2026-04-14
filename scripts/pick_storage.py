#!/usr/bin/env python3
"""
Connects to the Raspberry Pi, lists safe external storage devices,
prompts the user to pick one, then runs the mount_storage playbook.
"""

import sys
from pathlib import Path

import questionary
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from utils.ansible_utils import ANSIBLE_DIR, inventory_host_vars, make_connection, run_playbook  # noqa: E402
from utils.storage_utils import display_devices, get_block_devices, get_external_devices  # noqa: E402

PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"

console = Console()


def main() -> None:
    console.print("[bold]Fetching block devices from Raspberry Pi...[/bold]")

    hvars = inventory_host_vars()
    conn = make_connection(hvars)
    devices = get_external_devices(get_block_devices(conn))

    if not devices:
        console.print("[yellow]No external storage devices found.[/yellow]")
        return

    display_devices(devices)

    selected = questionary.select(
        "Select a device to mount:",
        choices=[
            questionary.Choice(title=f"/dev/{d.name}  {d.label or ''}  ({d.size or '?'})", value=d)
            for d in devices
        ],
    ).ask()
    if not selected:
        return

    label = questionary.text(
        "Mount point label (will mount at /mnt/<label>):",
        default=selected.label or selected.name,
    ).ask()
    if not label:
        return

    console.print(f"\n[bold green]Mounting /dev/{selected.name} at /mnt/{label}...[/bold green]")
    run_playbook(PLAYBOOK, device=f"/dev/{selected.name}", label=label)


if __name__ == "__main__":
    main()
