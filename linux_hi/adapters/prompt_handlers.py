"""PromptHandler protocol and built-in implementations."""

from __future__ import annotations

import os
from pathlib import Path
from string import Template
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


class PathHandler:
    """Path input with a default and shell-like expansion."""

    def prompt(self, label: str, default: str) -> str | None:
        """Return a normalized path, expanding '~' and env vars from the input."""
        value = questionary.path(label, default=default).ask()
        if value is None:
            return None
        expanded = value.strip()
        if not expanded:
            return expanded
        expanded = Template(expanded).safe_substitute(os.environ)
        return str(Path(expanded).expanduser().resolve(strict=False))


class PromptRegistryPort(Protocol):
    """Port for dispatching a prompt by type name."""

    def prompt(self, type_name: PromptType, label: str, default: str = "") -> str | None:
        """Return the entered value, or None if the operator aborted."""
        ...


class PromptRegistry:
    """Dispatch prompt calls to the registered handler for each type name."""

    def __init__(self, handlers: dict[str, PromptHandler]) -> None:
        """Initialise with a mapping of type names to handlers."""
        self._handlers = handlers

    def prompt(self, type_name: PromptType, label: str, default: str = "") -> str | None:
        """Dispatch to the handler registered for *type_name*."""
        if type_name not in self._handlers:
            raise ValueError(f"Unsupported prompt type: {type_name}")
        handler = self._handlers[type_name]
        return handler.prompt(label, default)
