"""Compatibility wrapper around yaml module.

Provides type-annotated access to yaml functions. For new code, import directly from yaml.
DEPRECATED: Import directly from yaml instead.
"""

from typing import Any, BinaryIO, TextIO

from yaml import dump, safe_dump, safe_load


def yaml_load(stream: str | BinaryIO | TextIO) -> Any:
    """Load YAML from a stream."""
    return safe_load(stream)


# Type-annotated aliases for compatibility
yaml_dump = dump
yaml_safe_load = safe_load
yaml_safe_dump = safe_dump

# Legacy import aliases
load = yaml_load
dump_alias = dump
safe_load_alias = safe_load
safe_dump_alias = safe_dump

__all__ = [
    "yaml_load",
    "yaml_dump",
    "yaml_safe_load",
    "yaml_safe_dump",
    "load",
    "dump_alias",
    "safe_load_alias",
    "safe_dump_alias",
]
