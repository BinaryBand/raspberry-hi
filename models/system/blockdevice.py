from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BlockDevice(BaseModel):
    name: str
    uuid: str | None = None
    path: str | None = None
    size: str | None = None
    type: str | None = None
    mountpoint: str | None = None
    label: str | None = None
    fstype: str | None = None
    children: list[BlockDevice] | None = None

    model_config = ConfigDict(extra="allow")


# Ensure forward refs are resolved for Pydantic v2
BlockDevice.model_rebuild()
