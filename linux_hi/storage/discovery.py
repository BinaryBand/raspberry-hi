"""Remote storage discovery helpers that execute commands on a connection."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from linux_hi.adapters.connection_types import RemoteConnection

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

__all__ = ["get_block_devices", "get_real_mounts"]
