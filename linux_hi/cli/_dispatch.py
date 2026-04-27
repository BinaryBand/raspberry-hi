"""Shared subcommand dispatch helper for CLI entry points."""

from __future__ import annotations

import sys
from collections.abc import Callable


def dispatch(
    subcommands: dict[str, Callable[[], None]],
    argv: list[str] | None = None,
) -> None:
    """Resolve and invoke a subcommand from *argv*, defaulting to 'list'."""
    args = argv if argv is not None else sys.argv[1:]
    subcmd = args[0] if args else "list"
    fn = subcommands.get(subcmd)
    if fn is None:
        sys.exit(f"Unknown subcommand '{subcmd}'. Available: {', '.join(subcommands)}")
    fn()
