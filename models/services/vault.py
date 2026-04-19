from typing import Optional

from pydantic import BaseModel, ConfigDict


class VaultSecrets(BaseModel):
    become_passwords: Optional[dict[str, str]] = None
    rclone_config: Optional[str] = None

    model_config = ConfigDict(extra="allow")
