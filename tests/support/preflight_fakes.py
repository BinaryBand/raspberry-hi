"""Test doubles for preflight orchestration ports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import PromptType


class FakePromptRegistry:
    """Returns pre-configured values without user interaction.

    Responses are keyed by prompt type (e.g. ``"text"``, ``"password"``,
    ``"rclone_remote"``).  A ``default`` fallback is returned for any type
    not explicitly configured.
    """

    def __init__(self, responses: dict[str, str] | None = None, default: str | None = None) -> None:
        """Initialise with type → value responses and an optional catch-all default."""
        self._responses = responses or {}
        self._default = default

    def prompt(self, type_name: PromptType | None, label: str, default: str = "") -> str | None:
        """Return the configured value for *type_name*, or the default."""
        return self._responses.get(type_name or "text", self._default)


class FakeHostVarsStore:
    """In-memory HostVarsPort that records writes for assertion."""

    def __init__(self, initial: dict[str, dict[str, object]] | None = None) -> None:
        """Initialise with optional pre-seeded host data."""
        self._data: dict[str, dict[str, object]] = initial or {}
        self.written: dict[str, dict[str, str]] = {}

    def read(self, hostname: str) -> dict[str, object]:
        """Return stored vars for *hostname*."""
        return dict(self._data.get(hostname, {}))

    def write(self, hostname: str, updates: dict[str, str]) -> None:
        """Record *updates* and merge into the in-memory store."""
        self.written[hostname] = updates
        self._data.setdefault(hostname, {}).update(updates)


class FakeVaultStore:
    """In-memory VaultPort that records writes for assertion."""

    def __init__(self, initial: dict[str, object] | None = None) -> None:
        """Initialise with optional pre-seeded vault data."""
        self._data: dict[str, object] = initial or {}
        self.written: list[dict[str, object]] = []

    def read(self) -> dict[str, object]:
        """Return a copy of the current in-memory vault."""
        return dict(self._data)

    def write(self, data: dict[str, object]) -> None:
        """Record the write and update the in-memory vault."""
        self.written.append(dict(data))
        self._data = dict(data)
