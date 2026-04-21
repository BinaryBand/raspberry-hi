from __future__ import annotations

from pathlib import Path

import yaml

from scripts.utils.yaml_utils import yaml_mapping


def role_required_vars(role_path: Path) -> list[str]:
    """Return names whose defaults/main.yml values are explicitly null."""
    defaults_file = role_path / "defaults" / "main.yml"
    if not defaults_file.exists():
        return []

    data = yaml_mapping(yaml.safe_load(defaults_file.read_text()), source=defaults_file)
    return [name for name, value in data.items() if value is None]
