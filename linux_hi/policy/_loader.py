"""Internal data-loading helpers shared across policy check modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from linux_hi.models.ansible.registry import AppRegistry, AppRegistryEntry
from linux_hi.models.policy import PolicyRegistry

Failures = list[str]


def _load_yaml(path: Path) -> object:
    """Load a YAML file and return the raw parsed object."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _as_dict(obj: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], obj) if isinstance(obj, dict) else None


def _as_list(obj: object) -> list[object] | None:
    return cast(list[object], obj) if isinstance(obj, list) else None


def _load_registry(registry_path: Path) -> dict[str, AppRegistryEntry]:
    """Load and validate the app registry, returning a mapping of app name to entry."""
    return AppRegistry.model_validate(_load_yaml(registry_path) or {}).apps


def _load_policy_registry(policy_registry_path: Path, failures: Failures) -> PolicyRegistry | None:
    """Load and validate the policy contract, appending to failures on error."""
    if not policy_registry_path.is_file():
        failures.append(f"Missing policy registry file: {policy_registry_path}")
        return None
    loaded = _load_yaml(policy_registry_path)
    try:
        return PolicyRegistry.model_validate(loaded or {})
    except ValidationError:
        failures.append(
            f"Invalid policy registry format in {policy_registry_path}: 'policies' must be a list"
        )
        return None
