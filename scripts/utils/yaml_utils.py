from typing import Any, BinaryIO, TextIO

from yaml import dump, safe_dump, safe_load


def yaml_load(stream: str | BinaryIO | TextIO) -> Any:
    return safe_load(stream)


yaml_dump = dump
yaml_safe_load = safe_load
yaml_safe_dump = safe_dump

# Compatibility shim for legacy imports
load = yaml_load
dump = yaml_dump
safe_load = yaml_safe_load
safe_dump = yaml_safe_dump

# This file re-exports all symbols from yaml
# to maintain backward compatibility with older codebases.
