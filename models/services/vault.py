from typing import Optional

from pydantic import BaseModel, ConfigDict


class VaultSecrets(BaseModel):
    minio_root_user: Optional[str] = None
    minio_root_password: Optional[str] = None
    become_passwords: Optional[dict[str, str]] = None

    model_config = ConfigDict(extra="allow")
