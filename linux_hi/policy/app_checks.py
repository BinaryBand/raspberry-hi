"""Policy checks for application roles and registry consistency."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ._loader import Failures, _load_registry, _load_yaml


def get_app_roles(apps_dir: Path) -> list[str]:
    """Return a list of application roles in the specified directory."""
    return [p.name for p in apps_dir.iterdir() if p.is_dir()]


def check_registry_entries(app_roles: list[str], registry_path: Path, failures: Failures) -> None:
    """Verify that all application roles are listed in the registry file."""
    if not registry_path.exists():
        failures.append(f"Missing registry file: {registry_path}")
        return
    registry = _load_registry(registry_path)
    for app in app_roles:
        if app not in registry:
            failures.append(f"App '{app}' missing from registry.yml")


def check_app_dirs(
    app_roles: list[str],
    apps_dir: Path,
    failures: Failures,
    registry_path: Path | None = None,
) -> None:
    """Check that each application role has required files and subdirectories."""
    registry = None
    if registry_path and registry_path.exists():
        registry = _load_registry(registry_path)

    for app in app_roles:
        app_path = apps_dir / app
        if not (app_path / "tasks").is_dir():
            failures.append(f"App '{app}' missing 'tasks/' directory")

        if registry is not None:
            entry = registry.get(app)
            needs_backup = entry.backup if entry is not None else True
            needs_restore = entry.restore if entry is not None else True
        else:
            needs_backup = needs_restore = True

        if needs_backup and not (app_path / "backup.yml").is_file():
            failures.append(f"App '{app}' missing 'backup.yml'")
        if needs_restore and not (app_path / "restore.yml").is_file():
            failures.append(f"App '{app}' missing 'restore.yml'")


def check_app_tests(
    app_roles: list[str], tests_dir: Path, e2e_dir: Path, failures: Failures
) -> None:
    """Ensure that each application role is covered by tests or e2e files."""
    test_file = tests_dir / "test_ansible_apps.py"
    e2e_files = list(e2e_dir.iterdir()) if e2e_dir.is_dir() else []
    test_content = test_file.read_text(encoding="utf-8") if test_file.exists() else ""

    for app in app_roles:
        found = app in test_content
        if not found:
            for ef in e2e_files:
                if ef.is_file() and app in ef.read_text(encoding="utf-8"):
                    found = True
                    break
        if not found:
            failures.append(f"App '{app}' missing test in test_ansible_apps.py or e2e/")


def check_registry_conflicts(
    app_roles: list[str], apps_dir: Path, registry_path: Path, failures: Failures
) -> None:
    """Fail on conflicting default values between registry.yml and role defaults."""
    if not registry_path.is_file():
        failures.append(f"Missing registry file: {registry_path}")
        return

    registry = _load_registry(registry_path)

    for app in app_roles:
        entry = registry.get(app)
        if entry is None:
            continue

        defaults_path = apps_dir / app / "defaults" / "main.yml"
        if not defaults_path.is_file():
            continue

        defaults_loaded = _load_yaml(defaults_path)
        defaults: dict[str, Any] = (
            cast(dict[str, Any], defaults_loaded) if isinstance(defaults_loaded, dict) else {}
        )

        for key in set(entry.preflight_vars.keys()) & set(defaults.keys()):
            role_default = defaults.get(key)
            var_spec = entry.preflight_vars.get(key)
            registry_default = var_spec.default if var_spec is not None else None

            if role_default is not None and registry_default is not None:
                if str(role_default) != str(registry_default):
                    failures.append(
                        f"Registry/role defaults conflict for app '{app}', var '{key}': "
                        f"registry default {registry_default!r} != role default {role_default!r}"
                    )


def check_app_playbooks(app_roles: list[str], apps_dir: Path, failures: Failures) -> None:
    """Ensure every registered app has a generated per-app playbook."""
    for app in app_roles:
        playbook = apps_dir / app / "playbook.yml"
        if not playbook.is_file():
            failures.append(
                f"App '{app}' missing per-app playbook: {playbook} "
                "(run 'make generate-apps' to regenerate)"
            )


def check_app_data_paths(app_roles: list[str], registry_path: Path, failures: Failures) -> None:
    """Ensure persistent apps declare explicit data paths in registry preflight vars."""
    if not registry_path.is_file():
        failures.append(f"Missing registry file: {registry_path}")
        return

    registry = _load_registry(registry_path)

    for app in app_roles:
        entry = registry.get(app)
        if entry is None:
            continue

        requires_declared_path = (
            entry.service_type == "containerized" or entry.backup or entry.restore
        )
        if not requires_declared_path:
            continue

        if not entry.preflight_vars:
            failures.append(
                f"App '{app}' requires persistence but declares no preflight_vars for data paths"
            )
            continue

        if not any("data_path" in key for key in entry.preflight_vars):
            failures.append(
                f"App '{app}' requires persistence but has no explicit '*_data_path' preflight var"
            )
