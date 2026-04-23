from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict


class VaultSecrets(BaseModel):
    become_passwords: Optional[dict[str, str]] = None
    # Store rclone config as a structured mapping: remote -> { key: value }
    rclone_config: Optional[Dict[str, Dict[str, str]]] = None
    restic_password: Optional[str] = None

    model_config = ConfigDict(extra="allow")
