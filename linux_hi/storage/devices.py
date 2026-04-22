"""Remote block-device discovery and mount helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, cast

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
    pass


def get_device_uuid(conn: RemoteConnection, device_path: str) -> str | None:
    """Return the UUID of a device (partition) by path, or None if not found."""
    import json

    from models.system.blockdevice import BlockDevice

    result = conn.run("lsblk -J -o NAME,UUID,PATH", hide=True)
    raw = json.loads(result.stdout)
    if isinstance(raw, dict):
        raw_dict = cast(dict[str, object], raw)
        blockdevices_obj = raw_dict.get("blockdevices", [])
        if isinstance(blockdevices_obj, list):
            raw_blockdevices: list[dict[str, object]] = []
            blockdevices_list = cast(list[object], blockdevices_obj)
            for item in blockdevices_list:
                if isinstance(item, dict):
                    raw_blockdevices.append(cast(dict[str, object], item))
        else:
            raw_blockdevices = []
    else:
        raw_blockdevices = []

    data: List[BlockDevice] = [BlockDevice.model_validate(d) for d in raw_blockdevices]

    def find_uuid(devs: List[BlockDevice]) -> str | None:
        for d in devs:
            if d.path == device_path:
                return d.uuid
            if d.children:
                u = find_uuid(d.children)
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
