from typing import Optional

from pydantic import BaseModel, ConfigDict


class HostVars(BaseModel):
    ansible_host: str
    ansible_user: Optional[str] = None
    ansible_port: Optional[int] = None
    ansible_ssh_private_key_file: Optional[str] = None

    model_config = ConfigDict(extra="allow")
