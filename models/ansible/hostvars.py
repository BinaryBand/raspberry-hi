from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict


class HostVars(BaseModel):
    ansible_host: str
    ansible_user: str | None = None
    ansible_port: int | None = None
    ansible_ssh_private_key_file: str | None = None

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_inventory(cls, hostname: str, data: Mapping[str, object] | None) -> "HostVars":
        """Build host vars from inventory data, falling back to the alias as host."""
        if not data:
            return cls(ansible_host=hostname)
        return cls.model_validate(dict(data))
