"""Fabric connection helpers backed by inventory host vars."""

from __future__ import annotations

from pathlib import Path

from fabric import Config, Connection

from linux_hi.models import ANSIBLE_DATA, HostVars


def make_connection(host: str | HostVars, *, become_password: str | None = None) -> Connection:
    """Create a Fabric connection from a host alias or validated HostVars."""
    host_vars = ANSIBLE_DATA.host_vars(host) if isinstance(host, str) else host

    connect_kwargs: dict[str, str] = {}
    if host_vars.ansible_ssh_private_key_file:
        key_path = Path(host_vars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ANSIBLE_DATA.root / key_path
        connect_kwargs["key_filename"] = str(key_path)

    config = (
        Config(overrides={"sudo": {"password": become_password}})
        if become_password is not None
        else None
    )

    return Connection(
        host=host_vars.ansible_host,
        user=host_vars.ansible_user,
        port=host_vars.ansible_port or 22,
        connect_kwargs=connect_kwargs,
        config=config,
    )


__all__ = ["Config", "Connection", "make_connection"]
