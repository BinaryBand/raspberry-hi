"""Remote block-device discovery and mount helpers."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, Callable

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.storage.discovery import get_block_devices, get_real_mounts
from linux_hi.storage.display import display_devices
from linux_hi.storage.policy import (
    DEFAULT_MOUNT_POLICY,
    SYSTEM_MOUNT_PREFIXES,
    MountPolicy,
    default_mount_policy,
    external_mounts,
    get_external_devices,
    is_system_device,
    mount_covering,
)

if TYPE_CHECKING:
    from models import BlockDevice

def get_device_uuid(conn: RemoteConnection, device_path: str) -> str | None:
    """Return the UUID of a device (partition) by path, or None if not found."""
    import json

    result = conn.run("lsblk -J -o NAME,UUID,PATH", hide=True)
    data: list[dict[str, Any]] = json.loads(result.stdout)["blockdevices"]

    def find_uuid(devs: list[dict[str, Any]]) -> str | None:
        for d in devs:
            if d.get("path") == device_path:
                return d.get("uuid")
            if d.get("children"):
                u = find_uuid(d["children"])
                if u:
                    return u
        return None

    return find_uuid(data)

__all__ = [
    "DEFAULT_MOUNT_POLICY",
    "SYSTEM_MOUNT_PREFIXES",
    "MountPolicy",
    "default_mount_policy",
    "display_devices",
    "external_mounts",
    "get_block_devices",
    "get_device_uuid",
    "get_external_devices",
    "get_real_mounts",
    "is_system_device",
    "mount_covering",
]
