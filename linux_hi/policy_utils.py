"""Utilities for repository policy checks."""

import os
from typing import Any, Dict, List, cast


def get_app_roles(apps_dir: str) -> List[str]:
    """Return a list of application roles in the specified directory."""
    return [d for d in os.listdir(apps_dir) if os.path.isdir(os.path.join(apps_dir, d))]


def check_registry_entries(app_roles: List[str], registry_path: str, failures: List[str]) -> None:
    """Verify that all application roles are listed in the registry file."""
    if not os.path.exists(registry_path):
        failures.append(f"Missing registry file: {registry_path}")
        return

    try:
        import yaml
    except ImportError:
        yaml = None

    with open(registry_path) as f:
        if yaml is None:
            lines = f.readlines()
            for app in app_roles:
                found = False
                in_apps = False
                for line in lines:
                    if line.strip() == "apps:":
                        in_apps = True
                    elif in_apps and line.strip().startswith(f"{app}:"):
                        found = True
                        break
                if not found:
                    failures.append(
                        f"App '{app}' missing from registry.yml "
                        "(YAML parser not installed, used fallback)"
                    )
        else:
            reg_data = yaml.safe_load(f)
            reg: Dict[str, Any] = cast(Dict[str, Any], reg_data) if reg_data else {}
            apps_section: Dict[str, Any] = {}
            if "apps" in reg:
                val = reg["apps"]
                if isinstance(val, dict):
                    apps_section = cast(Dict[str, Any], val)
            for app in app_roles:
                if app not in apps_section:
                    failures.append(f"App '{app}' missing from registry.yml")


def check_app_dirs(app_roles: List[str], apps_dir: str, failures: List[str]) -> None:
    """Check that each application role has the required subdirectories."""
    for app in app_roles:
        app_path = os.path.join(apps_dir, app)
        for subdir in ["backup", "restore", "tasks"]:
            if not os.path.isdir(os.path.join(app_path, subdir)):
                failures.append(f"App '{app}' missing '{subdir}/' directory")


def check_app_tests(
    app_roles: List[str], tests_dir: str, e2e_dir: str, failures: List[str]
) -> None:
    """Ensure that each application role is covered by tests or e2e files."""
    test_file = os.path.join(tests_dir, "test_ansible_apps.py")
    e2e_files = (
        [os.path.join(e2e_dir, f) for f in os.listdir(e2e_dir)] if os.path.isdir(e2e_dir) else []
    )
    test_content = open(test_file).read() if os.path.exists(test_file) else ""

    for app in app_roles:
        found = False
        if app in test_content:
            found = True
        else:
            for ef in e2e_files:
                if os.path.isfile(ef):
                    with open(ef) as f:
                        if app in f.read():
                            found = True
                            break
        if not found:
            failures.append(f"App '{app}' missing test in test_ansible_apps.py or e2e/")


def check_playbook_vars(ansible_dir: str, failures: List[str]) -> None:
    """Verify that variables are only defined in allowed directories."""
    for root, dirs, files in os.walk(ansible_dir):
        if "group_vars" in root or "host_vars" in root:
            continue
        # Use a list of directories to ignore to avoid B007
        _ = dirs
        for file in files:
            if not (file.endswith(".yml") or file.endswith(".yaml")):
                continue
            path = os.path.join(root, file)
            basename = os.path.basename(path)
            if basename == "registry.yml" or (basename == "main.yml" and "meta" in root):
                continue
            with open(path) as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    if stripped.endswith(":") and not stripped.startswith("-"):
                        if not stripped.startswith("---") and not stripped.startswith("#"):
                            failures.append(
                                f"Variable definition in {path}:{i} "
                                "(only allowed in group_vars/host_vars)"
                            )
