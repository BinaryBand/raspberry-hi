"""Info port abstractions for remote device and mount discovery."""

from __future__ import annotations

from typing import Protocol

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.models import BlockDevice, MountInfo


class InfoPort(Protocol):
    """Port for loading device and mount state from a host."""

    def list_devices(self, conn: RemoteConnection) -> list["BlockDevice"]:
        """Return the external block devices visible on the host."""
        ...

    def list_mounts(self, conn: RemoteConnection) -> list["MountInfo"]:
        """Return non-system mounts visible on the host."""
        ...


class RemoteInfoPort:
    """Adapter that sources data from the remote host via storage helpers."""

    def list_devices(self, conn: RemoteConnection) -> list["BlockDevice"]:
        """Load remote devices and filter out system disks."""
        from linux_hi.storage.discovery import get_block_devices
        from linux_hi.storage.policy import get_external_devices

        return get_external_devices(get_block_devices(conn))

    def list_mounts(self, conn: RemoteConnection) -> list["MountInfo"]:
        """Load remote mounts after system-path filtering."""
        from linux_hi.storage.discovery import get_real_mounts

        return get_real_mounts(conn)
