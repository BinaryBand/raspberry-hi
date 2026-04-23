"""Helpers for parsing rclone configuration (INI format)."""

from __future__ import annotations

import configparser
from typing import Dict


def parse_rclone_config(value: str | dict) -> Dict[str, Dict[str, str]]:
    """Return a mapping of remotes -> key/value mapping for *value*.

    Accepts either a raw INI string (old format) or a structured mapping
    (new format). Values are coerced to strings.
    """
    if isinstance(value, str):
        cfg = configparser.ConfigParser()
        cfg.read_string(value)
        result: Dict[str, Dict[str, str]] = {}
        for section in cfg.sections():
            # configparser returns lowercase keys by default; preserve as-is
            items = {k: v for k, v in cfg.items(section)}
            result[section] = {str(k): str(v) for k, v in items.items()}
        return result

    if isinstance(value, dict):
        result: Dict[str, Dict[str, str]] = {}
        for remote, mapping in value.items():
            if mapping is None:
                result[str(remote)] = {}
                continue
            if not isinstance(mapping, dict):
                raise TypeError("rclone config mapping values must be dicts")
            result[str(remote)] = {str(k): str(v) for k, v in mapping.items()}
        return result

    raise TypeError("Unsupported rclone config type: %r" % type(value))


def list_remotes(config_text: str | dict) -> list[str]:
    """Return all remote names defined in *config_text*.

    Accepts either a raw INI string (old behavior) or the structured mapping
    produced by :func:`parse_rclone_config`.
    """
    parsed = parse_rclone_config(config_text)
    return list(parsed.keys())


__all__ = ["parse_rclone_config", "list_remotes"]
