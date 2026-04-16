from pydantic import BaseModel, ConfigDict


class HostVars(BaseModel):
    ansible_host: str
    ansible_user: str | None = None
    ansible_port: int | None = None
    ansible_ssh_private_key_file: str | None = None

    model_config = ConfigDict(extra="allow")
