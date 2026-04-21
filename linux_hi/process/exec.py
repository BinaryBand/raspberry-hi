"""Small helpers to resolve executables and run subprocesses safely.

These helpers resolve the executable name to an absolute path using
``shutil.which`` before invoking ``subprocess.run``. This satisfies
linters that warn about starting processes with a partial executable
path and makes failures clearer when the executable is missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Iterable, List, cast


def resolve_executable(name: str) -> str:
    """Return an absolute path to *name* if it exists and is executable.

    If *name* already contains a path separator it is treated as a path
    and validated. Otherwise ``shutil.which`` is used.
    """
    if os.path.sep in name or name.startswith("."):
        path = os.path.expanduser(name)
        if os.path.exists(path) and os.access(path, os.X_OK):
            return os.path.abspath(path)
        raise FileNotFoundError(f"Executable not found or not executable: {name}")

    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(f"Executable not found in PATH: {name}")
    return path


def run_resolved(cmd: Iterable[str], /, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Resolve the command's executable and call ``subprocess.run``.

    The first element of *cmd* is resolved with :func:`resolve_executable`.
    All other positional and keyword arguments are forwarded to
    :func:`subprocess.run`.
    """
    cmd_list: List[str] = list(cmd)
    if not cmd_list:
        raise ValueError("empty command")

    exe = cmd_list[0]
    resolved = resolve_executable(exe)
    full_cmd = [resolved] + cmd_list[1:]
    return cast(subprocess.CompletedProcess[Any], subprocess.run(full_cmd, **kwargs))  # noqa: S603


__all__ = ["resolve_executable", "run_resolved"]
