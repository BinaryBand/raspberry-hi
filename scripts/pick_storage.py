#!/usr/bin/env python3
"""
Connects to the Raspberry Pi, lists safe external storage devices,
prompts the user to pick one, then runs the mount_storage playbook.
"""

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from fabric import Connection
from rich.console import Console
from rich.table import Table

# Ensure project root is importable when running script directly
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from models import BlockDevice, HostVars

ANSIBLE_DIR = Path(__file__).parent.parent / "ansible"
PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"


def _inventory_host_vars(host: str = "rpi") -> HostVars:
    """Read host vars from ansible-inventory so HOST/USER stay in one place."""
    # Run from ansible dir so ansible.cfg (and its relative inventory path) resolves correctly
    from exec_utils import run_resolved
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


SYSTEM_MOUNTS = {"/", "/boot", "/boot/firmware", "[SWAP]"}

console = Console()


def get_block_devices(host: str, user: str | None, key_file: str | None = None) -> list[BlockDevice]:
    connect_kwargs: dict = {}
    if key_file:
        connect_kwargs["key_filename"] = key_file
    conn = Connection(host=host, user=user, connect_kwargs=connect_kwargs)
    result = conn.run(
        "lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE",
        hide=True,
    )
    raw = json.loads(result.stdout)["blockdevices"]
    from models import BlockDevice

    return [BlockDevice.model_validate(d) for d in raw]


def is_system_device(device: BlockDevice) -> bool:
    """Return True if this device or any child is mounted at a system path."""
    if device.mountpoint in SYSTEM_MOUNTS:
        return True
    return any(is_system_device(child) for child in (device.children or []))


def collect_partitions(device: BlockDevice) -> list[BlockDevice]:
    """Return mountable partitions from a non-system disk."""
    children = device.children or []
    if children:
        return [c for c in children if c.type == "part" and c.fstype]
    if device.fstype:
        return [device]
    return []


def get_external_devices(devices: list[BlockDevice]) -> list[BlockDevice]:
    external = []
    for device in devices:
        if device.type != "disk" or is_system_device(device):
            continue
        external.extend(collect_partitions(device))
    return external


def display_devices(devices: list[BlockDevice]) -> None:
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
            f"/dev/{dev.name}",
            dev.label or "—",
            dev.size or "—",
            dev.fstype or "—",
            dev.mountpoint or "not mounted",
        )

    console.print(table)


def run_playbook(device: str, label: str) -> None:
    from exec_utils import run_resolved

    run_resolved(
        [
            "ansible-playbook",
            str(PLAYBOOK),
            "-e",
            f"device={device}",
            "-e",
            f"label={label}",
        ],
        cwd=str(PLAYBOOK.parent.parent),
        env={**os.environ, "ANSIBLE_CONFIG": str(ANSIBLE_DIR / "ansible.cfg")},
        check=True,
    )


def main() -> None:
    console.print("[bold]Fetching block devices from Raspberry Pi...[/bold]")

    hvars = _inventory_host_vars()
    key_file: str | None = None
    if hvars.ansible_ssh_private_key_file:
        key_path = Path(hvars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ROOT / key_path
        key_file = str(key_path)

    devices = get_external_devices(get_block_devices(hvars.ansible_host, hvars.ansible_user, key_file))

    if not devices:
        console.print("[yellow]No external storage devices found.[/yellow]")
        return

    display_devices(devices)

    choices = [
        questionary.Choice(
            title=f"/dev/{d.name}  {d.label or ''}  ({d.size or '?'})",
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

    device_path = f"/dev/{selected.name}"
    default_label = selected.label or selected.name

    label = questionary.text(
        "Mount point label (will mount at /mnt/<label>):",
        default=default_label,
    ).ask()

    if not label:
        return

    console.print(f"\n[bold green]Mounting {device_path} at /mnt/{label}...[/bold green]")
    run_playbook(device_path, label)


if __name__ == "__main__":
    main()
