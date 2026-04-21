def list_remotes(config_text: str) -> list[str]:
"""Compatibility shim: re-export list_remotes from linux_hi.storage.rclone."""
from linux_hi.storage.rclone import *
