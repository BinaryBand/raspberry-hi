#!/usr/bin/env python3
"""
Connects to the Raspberry Pi, lists safe external storage devices,
prompts the user to pick one, then runs the mount_storage playbook.
"""

import json
import subprocess
from pathlib import Path

import questionary
from fabric import Connection
from rich.console import Console
from rich.table import Table

ANSIBLE_DIR = Path(__file__).parent.parent / "ansible"


def _inventory_host_vars(host: str = "rpi") -> dict:
    """Read host vars from ansible-inventory so HOST/USER stay in one place."""
    # Run from project root so ansible.cfg paths resolve correctly
    PROJECT_ROOT = ANSIBLE_DIR.parent
    result = subprocess.run(
        ["ansible-inventory", "--host", host],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ansible-inventory failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


_hvars = _inventory_host_vars()
HOST = _hvars["ansible_host"]
USER = _hvars["ansible_user"]
PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"

SYSTEM_MOUNTS = {"/", "/boot", "/boot/firmware", "[SWAP]"}

console = Console()


def get_block_devices() -> list[dict]:
    conn = Connection(host=HOST, user=USER)
    result = conn.run(
        "lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE",
        hide=True,
    )
    return json.loads(result.stdout)["blockdevices"]


def is_system_device(device: dict) -> bool:
    """Return True if this device or any child is mounted at a system path."""
    if device.get("mountpoint") in SYSTEM_MOUNTS:
        return True
    return any(is_system_device(child) for child in device.get("children", []))


def collect_partitions(device: dict) -> list[dict]:
    """Return mountable partitions from a non-system disk."""
    children = device.get("children", [])
    if children:
        return [c for c in children if c["type"] == "part" and c.get("fstype")]
    if device.get("fstype"):
        return [device]
    return []


def get_external_devices(devices: list[dict]) -> list[dict]:
    external = []
    for device in devices:
        if device["type"] != "disk" or is_system_device(device):
            continue
        external.extend(collect_partitions(device))
    return external


def display_devices(devices: list[dict]) -> None:
    table = Table(title="Available External Storage", header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Device")
    table.add_column("Label")
    table.add_column("Size")
    table.add_column("Filesystem")
    table.add_column("Mount Point")

    for i, dev in enumerate(devices, start=1):
        table.add_row(
            str(i),
            f"/dev/{dev['name']}",
            dev.get("label") or "—",
            dev.get("size") or "—",
            dev.get("fstype") or "—",
            dev.get("mountpoint") or "not mounted",
        )

    console.print(table)


def run_playbook(device: str, label: str) -> None:
    subprocess.run(
        [
            "ansible-playbook",
            str(PLAYBOOK),
            "-e",
            f"device={device}",
            "-e",
            f"label={label}",
        ],
        cwd=ANSIBLE_DIR,
        check=True,
    )


def main() -> None:
    console.print("[bold]Fetching block devices from Raspberry Pi...[/bold]")

    devices = get_external_devices(get_block_devices())

    if not devices:
        console.print("[yellow]No external storage devices found.[/yellow]")
        return

    display_devices(devices)

    choices = [
        questionary.Choice(
            title=f"/dev/{d['name']}  {d.get('label') or ''}  ({d.get('size', '?')})",
            value=d,
        )
        for d in devices
    ]

    selected = questionary.select(
        "Select a device to mount:",
        choices=choices,
    ).ask()

    if not selected:
        return

    device_path = f"/dev/{selected['name']}"
    default_label = selected.get("label") or selected["name"]

    label = questionary.text(
        "Mount point label (will mount at /mnt/<label>):",
        default=default_label,
    ).ask()

    if not label:
        return

    console.print(
        f"\n[bold green]Mounting {device_path} at /mnt/{label}...[/bold green]"
    )
    run_playbook(device_path, label)


if __name__ == "__main__":
    main()
