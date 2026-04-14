from typing import Optional

from pydantic import BaseModel, ConfigDict


class MountInfo(BaseModel):
    """A single entry from findmnt output."""

    target: str
    source: Optional[str] = None
    fstype: Optional[str] = None
    size: Optional[str] = None

    model_config = ConfigDict(extra="allow")
