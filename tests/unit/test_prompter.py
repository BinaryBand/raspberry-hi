"""Unit tests for questionary-backed mount prompter adapter."""

from __future__ import annotations

from typing import Any

import pytest

from linux_hi.adapters.prompter import QuestionaryPrompter
from tests.support.builders import blk


def test_choose_device_returns_none_for_empty_device_list() -> None:
    """Choosing with no devices should immediately return None."""
    assert QuestionaryPrompter().choose_device([]) is None


def test_choose_device_displays_and_returns_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Choosing should render device list and return user-selected BlockDevice."""
    rendered: list[int] = []
    devices = [blk("sdb1", "part", "/mnt/usb", label="USB", size="1T")]

    monkeypatch.setattr(
        "linux_hi.storage.display.display_devices",
        lambda shown: rendered.append(len(shown)),
    )

    def _fake_select(_label: str, choices: list[Any]) -> object:
        selected = choices[0]
        return type("Q", (), {"ask": lambda self: selected.value})()

    monkeypatch.setattr("linux_hi.adapters.prompter.questionary.select", _fake_select)

    selected = QuestionaryPrompter().choose_device(devices)

    assert selected is devices[0]
    assert rendered == [1]


def test_ask_label_uses_default_and_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Label prompt should pass through default and return entered value."""
    monkeypatch.setattr(
        "linux_hi.adapters.prompter.questionary.text",
        lambda _label, default: type("Q", (), {"ask": lambda self: f"{default}-x"})(),
    )

    assert QuestionaryPrompter().ask_label("usb") == "usb-x"


def test_ask_label_normalizes_none_default_to_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Label prompt should normalize None default to an empty string."""
    seen_defaults: list[str] = []

    def _fake_text(_label: str, default: str) -> object:
        seen_defaults.append(default)
        return type("Q", (), {"ask": lambda self: "chosen"})()

    monkeypatch.setattr("linux_hi.adapters.prompter.questionary.text", _fake_text)

    assert QuestionaryPrompter().ask_label(None) == "chosen"
    assert seen_defaults == [""]
