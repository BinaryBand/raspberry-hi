from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MountInfo(BaseModel):
    """A single entry from findmnt output."""

    target: str
    source: str | None = None
    fstype: str | None = None
    size: str | None = None

    model_config = ConfigDict(extra="allow")
