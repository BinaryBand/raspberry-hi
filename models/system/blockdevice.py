from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class BlockDevice(BaseModel):
    name: str
    uuid: Optional[str] = None
    path: Optional[str] = None
    size: Optional[str] = None
    type: Optional[str] = None
    mountpoint: Optional[str] = None
    label: Optional[str] = None
    fstype: Optional[str] = None
    children: Optional[List["BlockDevice"]] = None

    model_config = ConfigDict(extra="allow")


# Ensure forward refs are resolved for Pydantic v2
BlockDevice.model_rebuild()
