"""Port/controller abstractions for interactive hosts and vault configuration."""

from __future__ import annotations

from typing import Protocol

HostRow = dict[str, str]
HostRows = list[HostRow]
VaultRows = list[tuple[str, str]]


class HostsConfigPort(Protocol):
    """Port for host inventory operations exposed to configuration commands."""

    def list(self) -> HostRows:
        """Return host rows suitable for display."""
        ...

    def add(
        self,
        *,
        name: str,
        address: str,
        user: str | None,
        port: int | None,
        secret: str | None,
        password: str,
    ) -> None:
        """Add one host and its associated auth material."""
        ...

    def remove(self, *, name: str) -> None:
        """Remove one host and its associated auth material."""
        ...


class VaultConfigPort(Protocol):
    """Port for vault key operations exposed to configuration commands."""

    def list(self) -> VaultRows:
        """Return top-level vault keys and value types."""
        ...

    def add(self, *, name: str, value: str) -> None:
        """Add or update a top-level vault key."""
        ...

    def remove(self, *, name: str) -> None:
        """Remove a top-level vault key."""
        ...


class HostsConfigController:
    """Public add/remove/list actions for host configuration workflows."""

    def __init__(self, port: HostsConfigPort) -> None:
        """Bind a host configuration port implementation."""
        self._port = port

    def list(self) -> HostRows:
        """Return host rows via the bound port."""
        return self._port.list()

    def add(
        self,
        *,
        name: str,
        address: str,
        user: str | None,
        port: int | None,
        secret: str | None,
        password: str,
    ) -> None:
        """Forward one host add operation to the bound port."""
        self._port.add(
            name=name,
            address=address,
            user=user,
            port=port,
            secret=secret,
            password=password,
        )

    def remove(self, *, name: str) -> None:
        """Forward one host removal operation to the bound port."""
        self._port.remove(name=name)


class VaultConfigController:
    """Public add/remove/list actions for vault configuration workflows."""

    def __init__(self, port: VaultConfigPort) -> None:
        """Bind a vault configuration port implementation."""
        self._port = port

    def list(self) -> VaultRows:
        """Return vault key/type rows via the bound port."""
        return self._port.list()

    def add(self, *, name: str, value: str) -> None:
        """Forward one vault key add/update operation to the bound port."""
        self._port.add(name=name, value=value)

    def remove(self, *, name: str) -> None:
        """Forward one vault key removal operation to the bound port."""
        self._port.remove(name=name)
