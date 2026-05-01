"""Tests for prompt handler behavior and prompt registry dispatch."""

from __future__ import annotations

import os

import pytest

from linux_hi.adapters.prompt_handlers import PathHandler, PromptRegistry


class _AskStub:
    def __init__(self, value: str | None) -> None:
        self._value = value

    def ask(self) -> str | None:
        return self._value


def test_path_handler_expands_home_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Path handler should expand user and env vars and normalize the path."""
    monkeypatch.setenv("HI_PATH_ROOT", "var-root")
    monkeypatch.setattr(
        "linux_hi.adapters.prompt_handlers.questionary.path",
        lambda label, default, **_: _AskStub("~/$HI_PATH_ROOT/../data"),
    )

    value = PathHandler().prompt("path:", "")

    assert value is not None
    assert "~" not in value
    assert "$HI_PATH_ROOT" not in value
    assert value.endswith(os.path.normpath("data"))


def test_path_handler_returns_none_on_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    """Path handler should return None when prompt is aborted."""
    monkeypatch.setattr(
        "linux_hi.adapters.prompt_handlers.questionary.path",
        lambda label, default, **_: _AskStub(None),
    )

    assert PathHandler().prompt("path:", "") is None


def test_path_handler_decorates_label_with_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Path handler should append the UX hint before the colon in the displayed label."""
    captured: list[str] = []
    monkeypatch.setattr(
        "linux_hi.adapters.prompt_handlers.questionary.path",
        lambda label, default, **_: captured.append(label) or _AskStub("/srv/data"),
    )

    PathHandler().prompt("  some_var (a hint):", "")

    assert len(captured) == 1
    label = captured[0]
    assert PathHandler._HINT in label
    assert label.endswith(":")
    # Original trailing colon should not be doubled
    assert "::" not in label


def test_prompt_registry_raises_on_unknown_type() -> None:
    """Prompt registry should fail fast for unsupported prompt types."""

    class _Handler:
        def prompt(self, label: str, default: str) -> str | None:
            return "ok"

    registry = PromptRegistry({"text": _Handler()})

    with pytest.raises(ValueError, match="Unsupported prompt type"):
        registry.prompt("path", "path:", "")
