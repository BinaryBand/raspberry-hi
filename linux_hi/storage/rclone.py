"""Helpers for parsing rclone configuration (INI format)."""

from __future__ import annotations

import configparser

def list_remotes(config_text: str) -> list[str]:
	"""Return all remote names defined in *config_text* (rclone INI format)."""
	cfg = configparser.ConfigParser()
	cfg.read_string(config_text)
	return list(cfg.sections())

__all__ = ["list_remotes"]
