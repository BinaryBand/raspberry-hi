from typing import Optional

from pydantic import BaseModel, ConfigDict


class VaultSecrets(BaseModel):
    minio_root_user: Optional[str] = None
    minio_root_password: Optional[str] = None
    rpi_become_password: Optional[str] = None
    debian_become_password: Optional[str] = None

    model_config = ConfigDict(extra="allow")
