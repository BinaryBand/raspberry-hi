"""Info port abstractions for remote device and mount discovery.

Provides a small `InfoPort` protocol and a `RemoteInfoPort` adapter that
delegates to the existing `storage_utils` helpers so discovery logic can be
reused and substituted in tests.
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
        from .storage_utils import get_block_devices, get_external_devices

        return get_external_devices(get_block_devices(conn))

    def list_mounts(self, conn: RemoteConnection) -> list["MountInfo"]:
        from .storage_utils import get_real_mounts

        return get_real_mounts(conn)
