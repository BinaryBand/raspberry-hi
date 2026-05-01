"""PromptHandler protocol and built-in implementations."""

from __future__ import annotations

from typing import Protocol

import questionary

from linux_hi.models import PromptType


class PromptHandler(Protocol):
    """Port for prompting a single value from the operator."""

    def prompt(self, label: str, default: str) -> str | None:
        """Return the entered value, or None if the operator aborted."""
        ...


class TextHandler:
    """Free-text input with an optional pre-filled default."""

    def prompt(self, label: str, default: str) -> str | None:
        """Return the text entered by the operator."""
        return questionary.text(label, default=default).ask()


class PasswordHandler:
    """Hidden password input."""

    def prompt(self, label: str, default: str) -> str | None:
        """Return the password entered by the operator."""
        return questionary.password(label).ask()


class PromptRegistryPort(Protocol):
    """Port for dispatching a prompt by type name."""

    def prompt(self, type_name: PromptType | None, label: str, default: str = "") -> str | None:
        """Return the entered value, or None if the operator aborted."""
        ...


class PromptRegistry:
    """Dispatch prompt calls to the registered handler for each type name."""

    def __init__(self, handlers: dict[str, PromptHandler]) -> None:
        """Initialise with a mapping of type names to handlers."""
        self._handlers = handlers

    def prompt(self, type_name: PromptType | None, label: str, default: str = "") -> str | None:
        """Dispatch to the handler registered for *type_name*, falling back to text."""
        handler = self._handlers.get(type_name or "text", self._handlers["text"])
        return handler.prompt(label, default)
