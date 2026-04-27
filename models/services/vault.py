from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VaultSecrets(BaseModel):
    become_passwords: dict[str, str] | None = None
    # Store rclone config as a structured mapping: remote -> { key: value }
    rclone_config: dict[str, dict[str, str]] | None = None
    restic_password: str | None = None

    model_config = ConfigDict(extra="allow")
