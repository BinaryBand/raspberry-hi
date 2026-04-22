"""Remote storage discovery helpers for fabric connections.

Provides functions to discover block devices and mount points on remote hosts
by executing commands over SSH via fabric connections.

These functions are specific to remote operations and fabric's Command Result
interface. They are NOT duplicated in linux_hi because linux_hi is designed for
local system operations only.

NOTE: This is NOT a re-export shim. This module contains intentional implementations
      specific to remote (fabric-based) operations.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .connection_types import RemoteConnection

if TYPE_CHECKING:
    from models import BlockDevice, MountInfo


def get_block_devices(conn: RemoteConnection) -> list[BlockDevice]:
    """Return all block devices reported by lsblk on the remote host."""
    from models import BlockDevice

    result = conn.run("lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE", hide=True)
    raw = json.loads(result.stdout)["blockdevices"]
    return [BlockDevice.model_validate(device) for device in raw]


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
