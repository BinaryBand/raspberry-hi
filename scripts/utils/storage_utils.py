"""Remote block-device discovery and mount helpers.

Functions here operate over a Fabric Connection so callers never need to
re-implement SSH setup or lsblk/findmnt parsing.
"""

from __future__ import annotations

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
]
