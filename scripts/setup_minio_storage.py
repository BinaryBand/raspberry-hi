#!/usr/bin/env python3
"""
Pre-flight for 'make site': ensures MinIO data will land on external storage.
If minio_data_path isn't on a non-root mount, guides the user through options
and writes the chosen configuration back to host_vars before Ansible runs.

Run via: make minio
"""

from __future__ import annotations

import sys

import questionary
from rich.console import Console
from utils.ansible_utils import (
    ANSIBLE_DIR,
    inventory_host_vars,
    make_connection,
    read_host_vars,
    read_role_defaults,
    run_playbook,
    update_host_vars,
)
from utils.storage_flows import flow_mount_new_device, flow_use_existing_mount, parse_path_hints
from utils.storage_utils import external_mounts, get_real_mounts

from models import MinioConfig

MOUNT_PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"

console = Console()


def main(host: str = "rpi") -> None:
    config = MinioConfig.model_validate({**read_role_defaults("minio"), **read_host_vars(host)})

    if not config.minio_require_external_mount:
        console.print(
            "[dim]MinIO external-mount check skipped (minio_require_external_mount: false).[/dim]"
        )
        return

    console.print("[bold]Checking MinIO storage configuration...[/bold]")

    hvars = inventory_host_vars(host)
    conn = make_connection(hvars)
    mounts = get_real_mounts(conn)

    label_hint, _ = parse_path_hints(config.minio_data_path)

    ext = external_mounts(mounts)
    choices = [questionary.Choice("Mount external storage", value="mount")]
    if ext:
        choices.append(questionary.Choice("Use a drive that's already mounted", value="existing"))
    choices.append(questionary.Choice("Abort", value="abort"))

    action = questionary.select(
        "How would you like to configure MinIO storage?", choices=choices
    ).ask()

    if action is None or action == "abort":
        sys.exit(1)

    if action == "mount":
        mount_result = flow_mount_new_device(conn, label_hint=label_hint)
        if mount_result:
            device_path, label = mount_result
            console.print(f"\n[bold green]Mounting {device_path} at /mnt/{label}...[/bold green]")
            run_playbook(MOUNT_PLAYBOOK, device=device_path, label=label)
            base = f"/mnt/{label}"
        else:
            base = None
    else:
        base = flow_use_existing_mount(mounts)

    if not base:
        console.print("[red]No mount point selected. Aborting.[/red]")
        sys.exit(1)

    subdir = questionary.text(
        "Subdirectory for MinIO data within the mount:",
        default="minio/data",
    ).ask()
    if not subdir:
        sys.exit(1)

    new_path = f"{base.rstrip('/')}/{subdir.strip('/')}"
    update_host_vars(host, minio_data_path=new_path, minio_require_external_mount=True)
    console.print(
        f"\n[bold green]Set minio_data_path: {new_path} and "
        "minio_require_external_mount: True in host_vars.[/bold green]"
    )


if __name__ == "__main__":
    import os

    main(host=os.environ.get("HOST", "rpi"))
