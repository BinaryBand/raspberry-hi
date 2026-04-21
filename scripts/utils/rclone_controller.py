"""Public access point for rclone setup orchestration."""

from __future__ import annotations

from scripts.internal.rclone_controller import RcloneSetupController

__all__ = ["RcloneSetupController"]
