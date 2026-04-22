"""Shared connection protocols for remote command execution.

Defines protocol types for remote connections and command results. These protocols
enable test stubbing and decoupling from the fabric library implementation.

All SSH-facing code should depend on these structural types instead of
importing ``fabric.Connection`` directly. Fabric satisfies the protocol as-is,
and tests can implement the same interface with lightweight fakes.

NOTE: This is an intentional design pattern module, not a re-export shim.
      Not deprecated—used for test abstraction.
"""

from __future__ import annotations

from typing import Any, Protocol


class CommandResult(Protocol):
    """Minimal result surface consumed by the project.

    Both ``fabric.Result`` and the test doubles only need to expose command
    stdout plus a success flag for the current helper set.
    """

    stdout: str
    ok: bool


class RemoteConnection(Protocol):
    """Minimal remote execution API shared by scripts and tests.

    ``run`` covers read-only commands used by discovery helpers. ``sudo`` is
    included because the interactive mount workflow performs privileged writes
    against the same connection object.
    """

    def run(
        self,
        command: str,
        *,
        hide: bool | str = False,
        warn: bool = False,
        echo: bool = False,
        in_stream: object | None = None,
        **kwargs: object,
    ) -> CommandResult: ...

    def sudo(
        self,
        command: str,
        *,
        user: str | None = None,
        hide: bool | str = False,
        warn: bool = False,
        **kwargs: Any,
    ) -> CommandResult: ...
