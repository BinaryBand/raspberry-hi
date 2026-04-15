"""SSH connection test doubles.

FakeConnection stubs fabric.Connection.run() — callers configure responses
per command prefix and never open a real socket.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeResult:
    """Test double for fabric.Result."""

    stdout: str
    ok: bool = True
    stderr: str = ""
    return_code: int = 0


class FakeConnection:
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

    def __init__(self, responses: dict[str, str | tuple[str, bool]]):
        self._responses = responses

    def run(
        self,
        command: str,
        *,
        hide: bool = False,
        warn: bool = False,
        **kwargs: object,
    ) -> FakeResult:
        for prefix, value in self._responses.items():
            if command.startswith(prefix):
                if isinstance(value, tuple):
                    stdout, ok = value
                else:
                    stdout, ok = value, True
                return FakeResult(stdout=stdout, ok=ok)
        return FakeResult(stdout="", ok=False)
