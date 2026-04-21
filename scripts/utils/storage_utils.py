def get_device_uuid(conn: RemoteConnection, device_path: str) -> str | None:
"""Compatibility shim: re-export storage helpers from linux_hi.storage.devices."""
from linux_hi.storage.devices import *
