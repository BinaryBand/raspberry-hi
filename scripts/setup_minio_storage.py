#!/usr/bin/env python3
"""
Pre-flight for 'make site': ensures MinIO data will land on external storage.
If minio_data_path isn't on a non-root mount, guides the user through options
and writes the chosen configuration back to host_vars before Ansible runs.
"""

import sys
from pathlib import Path

import questionary
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from models import MinioConfig  # noqa: E402
from utils.ansible_utils import (  # noqa: E402
    ANSIBLE_DIR,
    inventory_host_vars,
    make_connection,
    read_role_defaults,
    read_host_vars,
    run_playbook,
    update_host_vars,
)
from utils.storage_utils import (  # noqa: E402
    display_devices,
    external_mounts,
    get_block_devices,
    get_external_devices,
    get_real_mounts,
    mount_covering,
)

MOUNT_PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"
HOST = "rpi"

console = Console()


# ---------------------------------------------------------------------------
# Path hint parsing
# ---------------------------------------------------------------------------


def _parse_path_hints(minio_data_path: str) -> tuple[str | None, str | None]:
    """Extract (label_hint, subdir_hint) from a previously configured minio_data_path.

    /mnt/minio/minio/data  →  ("minio", "minio/data")
    /srv/minio/data        →  (None, None)
    """
    p = Path(minio_data_path)
    parts = p.parts
    if len(parts) >= 3 and parts[1] == "mnt":
        label = parts[2]
        subdir = str(Path(*parts[3:])) if len(parts) > 3 else None
        return label, subdir
    return None, None


# ---------------------------------------------------------------------------
# Interactive flows
# ---------------------------------------------------------------------------


def _flow_mount_new_device(conn, label_hint: str | None = None) -> str | None:
    """List external block devices, mount the chosen one, return its mount point."""
    devices = get_external_devices(get_block_devices(conn))

    if not devices:
        console.print("[yellow]No external storage devices found on the Pi.[/yellow]")
        return None

    display_devices(devices)

    selected = questionary.select(
        "Select a device to mount:",
        choices=[
            questionary.Choice(title=f"/dev/{d.name}  {d.label or ''}  ({d.size or '?'})", value=d)
            for d in devices
        ],
    ).ask()
    if not selected:
        return None

    label = questionary.text(
        "Mount point label (will mount at /mnt/<label>):",
        default=label_hint or selected.label or selected.name,
    ).ask()
    if not label:
        return None

    console.print(f"\n[bold green]Mounting /dev/{selected.name} at /mnt/{label}...[/bold green]")
    run_playbook(MOUNT_PLAYBOOK, device=f"/dev/{selected.name}", label=label)
    return f"/mnt/{label}"


def _flow_use_existing_mount(mounts) -> str | None:
    """Let the user pick from already-mounted external filesystems."""
    ext = external_mounts(mounts)
    if not ext:
        return None

    return questionary.select(
        "Select the mount point to use for MinIO data:",
        choices=[
            questionary.Choice(
                title=f"{fs.target}  ({fs.source or '?'}, {fs.fstype or '?'}, {fs.size or '?'})",
                value=fs.target,
            )
            for fs in ext
        ],
    ).ask()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    config = MinioConfig.model_validate({**read_role_defaults("minio"), **read_host_vars(HOST)})

    if not config.minio_require_external_mount:
        console.print("[dim]MinIO external-mount check skipped (minio_require_external_mount: false).[/dim]")
        return

    console.print("[bold]Checking MinIO storage configuration...[/bold]")

    hvars = inventory_host_vars(HOST)
    conn = make_connection(hvars)
    mounts = get_real_mounts(conn)
    covering = mount_covering(mounts, config.minio_data_path)

    if covering != "/":
        console.print(
            f"[green]MinIO data path [bold]{config.minio_data_path}[/bold] "
            f"is on external mount [bold]{covering}[/bold].[/green]"
        )
        return

    # Not on an external mount — guide the user
    ext = external_mounts(mounts)

    console.print(
        f"\n[yellow]MinIO data path [bold]{config.minio_data_path}[/bold] is not on an external mount.[/yellow]\n"
        "Storing MinIO data on an external drive protects against root-fs wear\n"
        "and keeps data separate from the OS.\n"
    )

    choices = [questionary.Choice("Mount external storage now", value="mount")]
    if ext:
        choices.append(questionary.Choice("Use a drive that's already mounted", value="existing"))
    choices += [
        questionary.Choice("Use root filesystem (not recommended)", value="skip"),
        questionary.Choice("Abort", value="abort"),
    ]

    action = questionary.select("How would you like to proceed?", choices=choices).ask()

    if action is None or action == "abort":
        sys.exit(1)

    if action == "skip":
        update_host_vars(HOST, minio_require_external_mount=False)
        console.print("[dim]Wrote minio_require_external_mount: false to host_vars. Continuing...[/dim]")
        return

    label_hint, subdir_hint = _parse_path_hints(config.minio_data_path)

    base = (
        _flow_mount_new_device(conn, label_hint=label_hint)
        if action == "mount"
        else _flow_use_existing_mount(mounts)
    )

    if not base:
        console.print("[red]No mount point selected. Aborting.[/red]")
        sys.exit(1)

    subdir = questionary.text(
        "Subdirectory for MinIO data within the mount:",
        default=subdir_hint or "minio/data",
    ).ask()
    if not subdir:
        sys.exit(1)

    new_path = f"{base.rstrip('/')}/{subdir.strip('/')}"
    update_host_vars(HOST, minio_data_path=new_path)
    console.print(f"\n[bold green]Set minio_data_path: {new_path} in host_vars.[/bold green]")


if __name__ == "__main__":
    main()
