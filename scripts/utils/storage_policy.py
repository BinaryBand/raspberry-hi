"""Compatibility shim: re-exports storage policy utilities from canonical location.

DEPRECATED: Import directly from linux_hi.storage.policy instead.
"""

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

__all__ = [
    "DEFAULT_MOUNT_POLICY",
    "SYSTEM_MOUNT_PREFIXES",
    "MountPolicy",
    "default_mount_policy",
    "external_mounts",
    "get_external_devices",
    "is_system_device",
    "mount_covering",
]
