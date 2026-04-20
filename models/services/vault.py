from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class VaultSecrets(BaseModel):
    become_passwords: Optional[dict[str, str]] = None
    rclone_config: Optional[str] = None
    restic_password: Optional[str] = None

    model_config = ConfigDict(extra="allow")
