"""SSH connection test doubles.

FakeConnection implements the shared RemoteConnection protocol without opening
real sockets. Callers configure responses per command prefix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.utils.connection_types import RemoteConnection


@dataclass
class FakeResult:
    """Test double for fabric.Result."""

    stdout: str
    ok: bool = True
    stderr: str = ""
    return_code: int = 0


class FakeConnection(RemoteConnection):
    """Test double for fabric.Connection.

    Accepts a dict mapping command prefixes to stdout strings or (stdout, ok)
    tuples. The first matching prefix wins, so more specific prefixes should
    appear first.

    Example::

        conn = FakeConnection({
            "lsblk": json.dumps({...}),
            "findmnt": ("", False),   # simulate a failed command
        })
    """

    def __init__(
        self,
        responses: dict[str, str | tuple[str, bool]],
        *,
        sudo_responses: dict[str, str | tuple[str, bool]] | None = None,
    ):
        """Initialize the connection with response mappings."""
        self._responses = responses
        self._sudo_responses = sudo_responses or responses

    def run(
        self,
        command: str,
        *,
        hide: bool | str = False,
        warn: bool = False,
        echo: bool = False,
        in_stream: object | None = None,
        **kwargs: object,
    ) -> FakeResult:
        """Stub for fabric.Connection.run()."""
        _ = (hide, warn, echo, in_stream, kwargs)
        return self._dispatch(command, self._responses)

    def sudo(
        self,
        command: str,
        *,
        user: str | None = None,
        hide: bool | str = False,
        warn: bool = False,
        echo: bool = False,
        in_stream: object | None = None,
        **kwargs: Any,
    ) -> FakeResult:
        """Stub for fabric.Connection.sudo()."""
        _ = (user, hide, warn, echo, in_stream, kwargs)
        return self._dispatch(command, self._sudo_responses)

    @staticmethod
    def _dispatch(
        command: str,
        responses: dict[str, str | tuple[str, bool]],
    ) -> FakeResult:
        """Return the first matching canned result for *command*."""
        for prefix, value in responses.items():
            if command.startswith(prefix):
                if isinstance(value, tuple):
                    stdout, ok = value
                else:
                    stdout, ok = value, True
                return FakeResult(stdout=stdout, ok=ok)
        return FakeResult(stdout="", ok=False)


class RecordingConnectionFactory:
    """Capture constructor kwargs when tests monkeypatch fabric.Connection."""

    def __init__(self, **kwargs: object) -> None:  # noqa: D107
        self.kwargs = kwargs
