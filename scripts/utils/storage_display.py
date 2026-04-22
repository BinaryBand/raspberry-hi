"""Compatibility shim: re-exports storage display utilities from canonical location.

DEPRECATED: Import directly from linux_hi.storage.display instead.
"""

from linux_hi.storage.display import display_devices

__all__ = ["display_devices"]
