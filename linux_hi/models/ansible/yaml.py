"""YAML boundary typing helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast


def yaml_mapping(data: object, *, source: Path) -> dict[str, Any]:
    """Return a string-keyed mapping loaded from a YAML document."""
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TypeError(f"Expected YAML mapping in {source}, got {type(data).__name__}")
    return cast(dict[str, Any], data)


__all__ = ["yaml_mapping"]
