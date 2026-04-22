"""Compatibility shim: re-exports storage utilities from canonical location.

DEPRECATED: Import directly from linux_hi.storage instead.
"""

from linux_hi.storage import (
    DEFAULT_MOUNT_POLICY,
    SYSTEM_MOUNT_PREFIXES,
    MountPolicy,
    default_mount_policy,
    display_devices,
    external_mounts,
    get_block_devices,
    get_device_uuid,
    get_external_devices,
    get_real_mounts,
    is_system_device,
    list_remotes,
    mount_covering,
)

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
    "list_remotes",
    "mount_covering",
]
