"""Info port abstractions for remote device and mount discovery.

DEPRECATED: This module is not actively used. Provides a protocol-based abstraction
for remote device and mount discovery, but the RemoteInfoPort implementation is not
imported anywhere in the current codebase.

If you need device/mount discovery, import directly from scripts.utils.storage_discovery
or linux_hi.storage for local operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .connection_types import RemoteConnection

if TYPE_CHECKING:
    from models import BlockDevice, MountInfo


class InfoPort(Protocol):
    def list_devices(self, conn: RemoteConnection) -> list["BlockDevice"]: ...

    def list_mounts(self, conn: RemoteConnection) -> list["MountInfo"]: ...


class RemoteInfoPort:
    """Adapter that sources data from the remote host via `storage_utils`.

    This is the default implementation used by the interactive scripts.
    """

    def list_devices(self, conn: RemoteConnection) -> list["BlockDevice"]:
        from .storage_discovery import get_block_devices
        from .storage_policy import get_external_devices

        return get_external_devices(get_block_devices(conn))

    def list_mounts(self, conn: RemoteConnection) -> list["MountInfo"]:
        from .storage_discovery import get_real_mounts

        return get_real_mounts(conn)
