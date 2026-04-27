"""Port abstractions for hosts and vault configuration."""

from __future__ import annotations

from typing import Protocol

HostRow = dict[str, str]
HostRows = list[HostRow]
VaultRows = list[tuple[str, str]]


class HostsConfigPort(Protocol):
    """Port for host inventory operations."""

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
    """Port for vault key operations."""

    def list(self) -> VaultRows:
        """Return top-level vault keys and value types."""
        ...

    def add(self, *, name: str, value: str) -> None:
        """Add or update a top-level vault key."""
        ...

    def remove(self, *, name: str) -> None:
        """Remove a top-level vault key."""
        ...
