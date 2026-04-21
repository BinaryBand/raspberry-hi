"""Remote block-device discovery and mount helpers.

Functions here operate over a Fabric Connection so callers never need to
re-implement SSH setup or lsblk/findmnt parsing.
"""

from __future__ import annotations

from typing import Any

from .connection_types import RemoteConnection
from .storage_discovery import get_block_devices, get_real_mounts
from .storage_display import display_devices
from .storage_policy import (
    DEFAULT_MOUNT_POLICY,
    SYSTEM_MOUNT_PREFIXES,
    MountPolicy,
    default_mount_policy,
    external_mounts,
    get_external_devices,
    is_system_device,
    mount_covering,
)


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
    "get_external_devices",
    "get_real_mounts",
    "is_system_device",
    "mount_covering",
    "get_device_uuid",
]
