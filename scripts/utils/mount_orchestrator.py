"""Compatibility shim: re-exports mount orchestration from canonical location.

DEPRECATED: Import directly from linux_hi.orchestration.mount instead.
"""

from __future__ import annotations

from linux_hi.orchestration.mount import MountOrchestrator

__all__ = ["MountOrchestrator"]
