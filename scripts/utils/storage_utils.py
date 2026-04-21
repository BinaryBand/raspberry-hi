"""Remote block-device discovery and mount helpers.

Functions here operate over a Fabric Connection so callers never need to
re-implement SSH setup or lsblk/findmnt parsing.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from rich.console import Console
from rich.table import Table

from .connection_types import RemoteConnection

if TYPE_CHECKING:
    from models import BlockDevice, MountInfo


# Virtual/kernel filesystem prefixes - never user data.
SYSTEM_MOUNT_PREFIXES = ("/sys", "/proc", "/dev", "/run")


MountPolicy = Callable[[str | None], bool]


def default_mount_policy(target: str | None) -> bool:
    """Return True when *target* should be treated as a system mount."""
    system_mounts = {"/", "/boot", "/boot/efi", "[SWAP]"}

    if not target:
        return False

    if target in system_mounts:
        return True

    # Catch distro variants such as /boot/firmware without hardcoding each one.
    if target.startswith("/boot/"):
        return True

    return any(target.startswith(prefix) for prefix in SYSTEM_MOUNT_PREFIXES)


DEFAULT_MOUNT_POLICY: MountPolicy = default_mount_policy

console = Console()


# ---------------------------------------------------------------------------
# Block device discovery
# ---------------------------------------------------------------------------


def get_block_devices(conn: RemoteConnection) -> list[BlockDevice]:
    """Return all block devices reported by lsblk on the remote host."""
    from models import BlockDevice

    result = conn.run("lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE", hide=True)
    raw = json.loads(result.stdout)["blockdevices"]
    return [BlockDevice.model_validate(d) for d in raw]


def is_system_device(
    device: BlockDevice,
    mount_policy: MountPolicy | None = None,
) -> bool:
    """Return True if *device* or any of its children is at a system mount point."""
    policy = mount_policy or DEFAULT_MOUNT_POLICY
    if policy(device.mountpoint):
        return True
    return any(is_system_device(child, policy) for child in (device.children or []))


def collect_partitions(device: BlockDevice) -> list[BlockDevice]:
    """Return mountable partitions from a non-system disk."""
    children = device.children or []
    if children:
        return [c for c in children if c.type == "part" and c.fstype]
    if device.fstype:
        return [device]
    return []


def get_external_devices(
    devices: list[BlockDevice],
    mount_policy: MountPolicy | None = None,
) -> list[BlockDevice]:
    """Filter *devices* down to mountable partitions on non-system disks."""
    policy = mount_policy or DEFAULT_MOUNT_POLICY
    external: list[BlockDevice] = []
    for device in devices:
        if device.type != "disk" or is_system_device(device, policy):
            continue
        external.extend(collect_partitions(device))
    return external


def display_devices(devices: list[BlockDevice]) -> None:
    """Print *devices* as a Rich table."""
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


# ---------------------------------------------------------------------------
# Mount discovery
# ---------------------------------------------------------------------------


def get_real_mounts(conn: RemoteConnection) -> list[MountInfo]:
    """Return all real (non-virtual) mount points on the remote host."""
    from models import MountInfo

    result = conn.run(
        "findmnt -J -o TARGET,SOURCE,FSTYPE,SIZE --real 2>/dev/null",
        hide=True,
        warn=True,
    )
    if not result.ok or not result.stdout.strip():
        return []
    return [MountInfo.model_validate(fs) for fs in json.loads(result.stdout).get("filesystems", [])]


def mount_covering(mounts: list[MountInfo], path: str) -> str:
    """Return the most-specific mount point that covers *path*.

    Works purely on the in-memory mount list — no SSH required. Safe to call
    even when *path* does not yet exist on the remote host.
    """
    covering = "/"
    for fs in mounts:
        normalised = fs.target.rstrip("/")
        if path == normalised or path.startswith(normalised + "/"):
            if len(fs.target) > len(covering):
                covering = fs.target
    return covering


def external_mounts(
    mounts: list[MountInfo],
    mount_policy: MountPolicy | None = None,
) -> list[MountInfo]:
    """Filter *mounts* to non-root, non-system entries."""
    policy = mount_policy or DEFAULT_MOUNT_POLICY
    return [fs for fs in mounts if not policy(fs.target)]
