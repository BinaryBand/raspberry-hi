"""Pure storage classification helpers.

These helpers operate on validated model objects and contain no remote I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from models import BlockDevice, MountInfo


SYSTEM_MOUNT_PREFIXES = ("/sys", "/proc", "/dev", "/run")

MountPolicy = Callable[[str | None], bool]


def default_mount_policy(target: str | None) -> bool:
    """Return True when *target* should be treated as a system mount."""
    system_mounts = {"/", "/boot", "/boot/efi", "[SWAP]"}

    if not target:
        return False

    if target in system_mounts:
        return True

    if target.startswith("/boot/"):
        return True

    return any(target.startswith(prefix) for prefix in SYSTEM_MOUNT_PREFIXES)


DEFAULT_MOUNT_POLICY: MountPolicy = default_mount_policy


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
        return [child for child in children if child.type == "part" and child.fstype]
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


def mount_covering(mounts: list[MountInfo], path: str) -> str:
    """Return the most-specific mount point that covers *path*."""
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
