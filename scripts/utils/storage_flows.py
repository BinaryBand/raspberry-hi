"""Interactive storage-selection flows shared by setup scripts.

Each function presents a TUI prompt (questionary + rich) and returns a value
the caller can act on, keeping orchestration logic out of the flow functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from rich.console import Console

from utils.storage_utils import (
    display_devices,
    external_mounts,
    get_block_devices,
    get_external_devices,
)

if TYPE_CHECKING:
    from fabric import Connection

    from models import MountInfo

console = Console()


# ---------------------------------------------------------------------------
# Path hint parsing
# ---------------------------------------------------------------------------


def parse_path_hints(minio_data_path: str) -> tuple[str | None, str | None]:
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


def flow_mount_new_device(
    conn: Connection, label_hint: str | None = None
) -> tuple[str, str] | None:
    """List external block devices and prompt the user to select one.

    Returns ``(device_path, label)`` — e.g. ``("/dev/sda1", "myusb")`` — so
    the caller can run the mount playbook and compute the mount point.
    Returns ``None`` if the user cancels at any step.
    """
    devices = get_external_devices(get_block_devices(conn))

    if not devices:
        console.print("[yellow]No external storage devices found on the target host.[/yellow]")
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

    return f"/dev/{selected.name}", label


def flow_use_existing_mount(mounts: list[MountInfo]) -> str | None:
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
