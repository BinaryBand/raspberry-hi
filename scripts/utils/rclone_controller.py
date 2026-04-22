"""Compatibility shim: re-exports rclone setup orchestration from canonical location.

DEPRECATED: Import directly from linux_hi.orchestration.rclone instead.
"""

from __future__ import annotations

from linux_hi.orchestration.rclone import RcloneSetupController

__all__ = ["RcloneSetupController"]
