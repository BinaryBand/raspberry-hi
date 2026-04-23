from __future__ import annotations

import configparser
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class VaultSecrets(BaseModel):
    become_passwords: Optional[dict[str, str]] = None
    # Accept either the old raw INI string or the new structured mapping:
    rclone_config: Optional[str | Dict[str, Dict[str, str]]] = None
    restic_password: Optional[str] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("rclone_config", mode="before")
    def _coerce_rclone_config(self, v):
        """Coerce an INI-string rclone config into a mapping (if possible).

        This keeps backwards compatibility for vault entries that still
        contain the raw INI blob while preferring the structured mapping
        representation for new writes.
        """
        if v is None:
            return v

        # If it's already a mapping, ensure it's nested dicts of strings
        if isinstance(v, dict):
            return {
                str(k): {str(kk): str(vv) for kk, vv in mapping.items()} for k, mapping in v.items()
            }

        # If it's a string, try to parse it as INI and return a mapping.
        if isinstance(v, str):
            cfg = configparser.ConfigParser()
            try:
                cfg.read_string(v)
            except Exception:
                # Return the original string if parsing fails
                return v
            result: dict[str, dict[str, str]] = {}
            for section in cfg.sections():
                result[section] = {k: v for k, v in cfg.items(section)}
            return result

        return v
