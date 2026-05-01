"""Unit tests for executable resolution and subprocess wrapper helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.utils import exec as exec_utils


def test_resolve_executable_accepts_explicit_executable_path(tmp_path: Path) -> None:
    """Explicit executable paths should resolve to absolute filesystem paths."""
    exe = tmp_path / "tool"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o755)

    resolved = exec_utils.resolve_executable(str(exe))

    assert resolved == str(exe.resolve())


def test_resolve_executable_rejects_non_executable_path(tmp_path: Path) -> None:
    """Explicit non-executable paths should raise FileNotFoundError."""
    exe = tmp_path / "tool"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o644)

    with pytest.raises(FileNotFoundError):
        exec_utils.resolve_executable(str(exe))


def test_resolve_executable_uses_which(monkeypatch: pytest.MonkeyPatch) -> None:
    """Named executables should resolve through shutil.which."""
    monkeypatch.setattr(exec_utils.shutil, "which", lambda _name: "/usr/bin/tool")

    assert exec_utils.resolve_executable("tool") == "/usr/bin/tool"


def test_resolve_executable_raises_when_not_in_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing named executables should raise FileNotFoundError."""
    monkeypatch.setattr(exec_utils.shutil, "which", lambda _name: None)

    with pytest.raises(FileNotFoundError):
        exec_utils.resolve_executable("missing-tool")


def test_run_resolved_rejects_empty_command() -> None:
    """run_resolved should fail fast on empty command sequences."""
    with pytest.raises(ValueError):
        exec_utils.run_resolved([])


def test_run_resolved_invokes_subprocess_with_resolved_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_resolved should replace argv0 with resolved path and forward kwargs."""
    calls: list[tuple[list[str], dict[str, object]]] = []

    class _Result:
        """Subprocess result stub for wrapper tests."""

        returncode = 0

    monkeypatch.setattr(exec_utils, "resolve_executable", lambda _name: "/usr/bin/tool")

    def _fake_run(cmd: list[str], **kwargs: object) -> _Result:
        calls.append((cmd, dict(kwargs)))
        return _Result()

    monkeypatch.setattr(exec_utils.subprocess, "run", _fake_run)

    result = exec_utils.run_resolved(["tool", "--flag"], capture_output=True, text=True)

    assert result.returncode == 0
    assert calls == [(["/usr/bin/tool", "--flag"], {"capture_output": True, "text": True})]
