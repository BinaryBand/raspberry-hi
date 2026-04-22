"""Utilities for repository policy checks."""

import os
from pathlib import Path
from typing import Any, Dict, List, cast

import yaml


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


def check_app_dirs(
    app_roles: List[str],
    apps_dir: str,
    failures: List[str],
    registry_path: str | None = None,
) -> None:
    """Check that each application role has required subdirectories.

    If a registry path is provided, backup/restore requirements are derived from
    each app's lifecycle flags. Otherwise, backup/restore/tasks are required.
    """
    apps_section: Dict[str, Any] = {}
    if registry_path and os.path.exists(registry_path):
        with open(registry_path) as registry_file:
            reg_data = yaml.safe_load(registry_file)
        reg = cast(Dict[str, Any], reg_data) if isinstance(reg_data, dict) else {}
        apps_val = reg.get("apps", {})
        if isinstance(apps_val, dict):
            apps_section = cast(Dict[str, Any], apps_val)

    for app in app_roles:
        app_path = os.path.join(apps_dir, app)
        required_dirs = ["tasks"]

        app_entry = apps_section.get(app)
        if isinstance(app_entry, dict):
            app_entry_map = cast(Dict[str, Any], app_entry)
            if bool(app_entry_map.get("backup", False)):
                required_dirs.append("backup")
            if bool(app_entry_map.get("restore", False)):
                required_dirs.append("restore")
        else:
            required_dirs.extend(["backup", "restore"])

        for subdir in required_dirs:
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
    """Verify that root-level playbooks do not define top-level vars blocks."""
    ansible_root = Path(ansible_dir)
    for path in sorted(ansible_root.glob("*.yml")) + sorted(ansible_root.glob("*.yaml")):
        if path.name == "registry.yml":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            # Play-level vars blocks in root playbooks are forbidden; role task vars are allowed.
            if line.startswith("  vars:"):
                failures.append(
                    f"Playbook vars block in {path}:{line_no} "
                    "(variables are only allowed in group_vars/host_vars)"
                )


def check_deleted_compatibility_namespaces(root_dir: str, failures: List[str]) -> None:
    """Ensure removed compatibility namespaces do not reappear under scripts/."""
    scripts_dir = Path(root_dir) / "scripts"
    for namespace in ("internal", "utils"):
        namespace_path = scripts_dir / namespace
        if namespace_path.exists():
            failures.append(
                f"Removed compatibility namespace reintroduced: {namespace_path} "
                "(use linux_hi responsibility packages instead)"
            )


def check_scripts_wrapper_topology(root_dir: str, failures: List[str]) -> None:
    """Validate that top-level script entrypoints remain thin CLI wrappers."""
    scripts_dir = Path(root_dir) / "scripts"
    if not scripts_dir.is_dir():
        failures.append(f"Missing scripts directory: {scripts_dir}")
        return

    for script_path in sorted(scripts_dir.glob("*.py")):
        if script_path.name == "__init__.py":
            continue

        module = script_path.stem
        text = script_path.read_text(encoding="utf-8")
        required_import = f"from linux_hi.cli.{module} import main"

        if required_import not in text:
            failures.append(
                f"{script_path} must import main from linux_hi.cli.{module} "
                f"(expected: '{required_import}')"
            )

        if 'if __name__ == "__main__":' not in text:
            failures.append(f"{script_path} missing __main__ entrypoint guard")
            continue

        guard_index = text.find('if __name__ == "__main__":')
        if "main(" not in text[guard_index:]:
            failures.append(f"{script_path} must invoke main(...) under __main__ guard")


def check_policy_registry_controls(policy_registry_path: str, failures: List[str]) -> None:
    """Ensure every enforced policy has at least one explicit control target."""
    registry_path = Path(policy_registry_path)
    if not registry_path.is_file():
        failures.append(f"Missing policy registry file: {registry_path}")
        return

    loaded: Any = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    data: Dict[str, Any] = cast(Dict[str, Any], loaded) if isinstance(loaded, dict) else {}
    raw_policies_obj: Any = data.get("policies", [])
    if not isinstance(raw_policies_obj, list):
        failures.append(
            f"Invalid policy registry format in {registry_path}: 'policies' must be a list"
        )
        return
    raw_policies: List[object] = cast(List[object], raw_policies_obj)

    for idx, policy_obj in enumerate(raw_policies, start=1):
        if not isinstance(policy_obj, dict):
            failures.append(f"Invalid policy entry #{idx} in {registry_path}: expected mapping")
            continue

        policy_map: Dict[str, Any] = cast(Dict[str, Any], policy_obj)

        policy_id = str(policy_map.get("id", f"policy-{idx}"))
        status = str(policy_map.get("status", "advisory")).lower()
        controls_obj: Any = policy_map.get("controls", [])
        if status != "enforced":
            continue
        if not isinstance(controls_obj, list):
            failures.append(f"Policy '{policy_id}' is marked enforced but has no control targets")
            continue
        controls: List[object] = cast(List[object], controls_obj)
        if len(controls) == 0:
            failures.append(f"Policy '{policy_id}' is marked enforced but has no control targets")


def check_makefile_host_selector(makefile_path: str, failures: List[str]) -> None:
    """Ensure operator-facing Makefile host selector conventions remain present."""
    makefile = Path(makefile_path)
    if not makefile.is_file():
        failures.append(f"Missing Makefile: {makefile}")
        return

    text = makefile.read_text(encoding="utf-8")
    if "HOST ?=" not in text:
        failures.append("Makefile must define a default HOST selector using 'HOST ?='")

    if "HOST defaults to 'rpi'" not in text:
        failures.append("Makefile help must document the default HOST selector")
