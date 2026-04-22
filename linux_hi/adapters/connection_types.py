"""Shared connection protocols for remote command execution."""

from __future__ import annotations

from typing import Protocol


class CommandResult(Protocol):
    """Minimal result surface consumed by the project."""

    stdout: str
    ok: bool


class RemoteConnection(Protocol):
    """Minimal remote execution API shared by scripts and tests."""

    def run(
        self,
        command: str,
        *,
        hide: bool | str = False,
        warn: bool = False,
        echo: bool = False,
        in_stream: object | None = None,
        **kwargs: object,
    ) -> CommandResult:
        """Execute a remote command without privilege escalation."""
        ...

    def sudo(
        self,
        command: str,
        *,
        user: str | None = None,
        hide: bool | str = False,
        warn: bool = False,
        echo: bool = False,
        in_stream: object | None = None,
        **kwargs: object,
    ) -> CommandResult:
        """Execute a remote command with privilege escalation."""
        ...
