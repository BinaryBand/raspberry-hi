"""Helpers for parsing rclone configuration (INI format).

This module enforces the structured representation: a mapping of
remote-name -> { key: value }.
"""

from __future__ import annotations

import configparser


def parse_rclone_ini(ini_text: str) -> dict[str, dict[str, str]]:
    """Parse a raw rclone INI string into a mapping of remotes.

    Empty or whitespace-only input returns an empty mapping. Invalid INI
    raises ValueError.
    """
    if not isinstance(ini_text, str):
        raise TypeError("parse_rclone_ini expects a string")

    if not ini_text.strip():
        return {}

    cfg = configparser.ConfigParser()
    try:
        cfg.read_string(ini_text)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Invalid rclone INI") from exc

    result: dict[str, dict[str, str]] = {}
    for section in cfg.sections():
        items = {k: v for k, v in cfg.items(section)}
        result[section] = {str(k): str(v) for k, v in items.items()}
    return result


def list_remotes(rclone_config: dict[str, dict[str, str]]) -> list[str]:
    """Return remote names from a structured `rclone_config` mapping.

    The function expects a mapping as produced by :func:`parse_rclone_ini`
    or read from the vault. Passing other types raises ``TypeError``.
    """
    if not isinstance(rclone_config, dict):
        raise TypeError("list_remotes expects a mapping of remotes")
    return list(rclone_config.keys())


__all__ = ["parse_rclone_ini", "list_remotes"]
