"""Helpers for ruamel.yaml round-trip YAML writing with style control."""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString


def dump_host_vars_yaml(data: dict[str, Any], path: Path) -> None:
    """Write host_vars YAML, preserving style and enforcing double quotes for ansible_become_password."""
    yaml = YAML()
    yaml.preserve_quotes = True
    # Force ansible_become_password to be double-quoted if present
    if "ansible_become_password" in data:
        val = data["ansible_become_password"]
        # Only re-wrap if not already a DoubleQuotedScalarString
        if not isinstance(val, DoubleQuotedScalarString):
            data["ansible_become_password"] = DoubleQuotedScalarString(str(val))
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)
