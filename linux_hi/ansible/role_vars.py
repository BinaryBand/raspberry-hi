"""Role default variable introspection helpers."""

from pathlib import Path

import yaml

from models.ansible.yaml import yaml_mapping


def role_required_vars(role_path: Path) -> list[str]:
    """Return names of variables in defaults/main.yml whose value is null.

    A null value (``~``) signals that the variable is required and must be
    set in host_vars before provisioning.
    """
    defaults_file = role_path / "defaults" / "main.yml"
    if not defaults_file.exists():
        return []
    with defaults_file.open() as fh:
        raw = yaml.safe_load(fh)
    defaults = yaml_mapping(raw, source=defaults_file)
    return [key for key, value in defaults.items() if value is None]


__all__ = ["role_required_vars"]
