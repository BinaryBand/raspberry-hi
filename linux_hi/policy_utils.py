"""Utilities for repository policy checks."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, cast

import yaml
from pydantic import ValidationError

from models.ansible.registry import AppRegistry, AppRegistryEntry, PreflightVarSpec
from models.policy import PolicyRegistry


def get_app_roles(apps_dir: Path) -> List[str]:
    """Return a list of application roles in the specified directory."""
    return [p.name for p in apps_dir.iterdir() if p.is_dir()]


def check_registry_entries(app_roles: List[str], registry_path: Path, failures: List[str]) -> None:
    """Verify that all application roles are listed in the registry file."""
    if not registry_path.exists():
        failures.append(f"Missing registry file: {registry_path}")
        return

    loaded = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    apps_section: Dict[str, Any] = {}
    # Prefer typed validation via AppRegistry, fallback to dict parsing
    try:
        reg_typed: AppRegistry = AppRegistry.model_validate(loaded or {})
        for app in app_roles:
            if app not in reg_typed.apps:
                failures.append(f"App '{app}' missing from registry.yml")
    except ValidationError:
        reg_dict: Dict[str, Any] = cast(Dict[str, Any], loaded) if loaded else {}
        apps_val = reg_dict.get("apps", {})
        if isinstance(apps_val, dict):
            apps_section = cast(Dict[str, Any], apps_val)
        for app in app_roles:
            if app not in apps_section:
                failures.append(f"App '{app}' missing from registry.yml")


def check_app_dirs(
    app_roles: List[str],
    apps_dir: Path,
    failures: List[str],
    registry_path: Path | None = None,
) -> None:
    """Check that each application role has required subdirectories.

    If a registry path is provided, backup/restore requirements are derived from
    each app's lifecycle flags. Otherwise, backup/restore/tasks are required.
    """
    apps_section: Dict[str, Any] = {}
    apps_registry: dict[str, AppRegistryEntry] | None = None
    if registry_path and registry_path.exists():
        reg_data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        # Try typed validation first.
        try:
            reg_typed: AppRegistry = AppRegistry.model_validate(reg_data or {})
            apps_registry = reg_typed.apps
        except ValidationError:
            reg_dict = cast(Dict[str, Any], reg_data) if isinstance(reg_data, dict) else {}
            apps_val = reg_dict.get("apps", {})
            if isinstance(apps_val, dict):
                apps_section = cast(Dict[str, Any], apps_val)

    for app in app_roles:
        app_path = apps_dir / app
        required_dirs = ["tasks"]

        if apps_registry is not None:
            entry = apps_registry.get(app)
            if entry is not None:
                if bool(entry.backup):
                    required_dirs.append("backup")
                if bool(entry.restore):
                    required_dirs.append("restore")
            else:
                required_dirs.extend(["backup", "restore"])
        else:
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
            if not (app_path / subdir).is_dir():
                failures.append(f"App '{app}' missing '{subdir}/' directory")


def check_app_tests(
    app_roles: List[str], tests_dir: Path, e2e_dir: Path, failures: List[str]
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


def check_playbook_vars(ansible_dir: Path, failures: List[str]) -> None:
    """Verify that root-level playbooks do not define top-level vars blocks."""
    for path in sorted(ansible_dir.glob("*.yml")) + sorted(ansible_dir.glob("*.yaml")):
        if path.name == "registry.yml":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            # Play-level vars blocks in root playbooks are forbidden; role task vars are allowed.
            if line.startswith("  vars:"):
                failures.append(
                    f"Playbook vars block in {path}:{line_no} "
                    "(variables are only allowed in group_vars/host_vars)"
                )


def check_policy_registry_controls(policy_registry_path: Path, failures: List[str]) -> None:
    """Ensure every enforced policy has at least one explicit control target."""
    if not policy_registry_path.is_file():
        failures.append(f"Missing policy registry file: {policy_registry_path}")
        return

    loaded = yaml.safe_load(policy_registry_path.read_text(encoding="utf-8"))
    try:
        reg = PolicyRegistry.model_validate(loaded or {})
    except ValidationError:
        failures.append(
            f"Invalid policy registry format in {policy_registry_path}: 'policies' must be a list"
        )
        return

    for idx, policy in enumerate(reg.policies, start=1):
        policy_id = policy.id or f"policy-{idx}"
        status = (policy.status or "advisory").lower()
        if status != "enforced":
            continue
        controls = policy.controls
        if not controls:
            failures.append(f"Policy '{policy_id}' is marked enforced but has no control targets")


def check_makefile_host_selector(makefile_path: Path, failures: List[str]) -> None:
    """Ensure operator-facing Makefile host selector conventions remain present."""
    if not makefile_path.is_file():
        failures.append(f"Missing Makefile: {makefile_path}")
        return

    text = makefile_path.read_text(encoding="utf-8")
    if "HOST ?=" not in text:
        failures.append("Makefile must define a default HOST selector using 'HOST ?='")

    if "HOST defaults to 'rpi'" not in text:
        failures.append("Makefile help must document the default HOST selector")


def check_registry_conflicts(
    app_roles: List[str], apps_dir: Path, registry_path: Path, failures: List[str]
) -> None:
    """Fail on conflicting default values between registry.yml and role defaults.

    Compare `ansible/apps/<app>/defaults/main.yml` against the entry in
    *registry_path* under `apps.<app>.preflight_vars`. If both sources declare a
    non-null default for the same variable and the values differ, record a
    failure.
    """
    if not registry_path.is_file():
        failures.append(f"Missing registry file: {registry_path}")
        return

    loaded = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    apps_section: Dict[str, Any] = {}
    apps_section_typed: dict[str, AppRegistryEntry] | None = None
    # Prefer typed AppRegistry when possible
    try:
        reg_typed: AppRegistry = AppRegistry.model_validate(loaded or {})
        apps_section_typed = reg_typed.apps
    except ValidationError:
        reg_dict: Dict[str, Any] = cast(Dict[str, Any], loaded) if isinstance(loaded, dict) else {}
        apps_val = reg_dict.get("apps", {})
        if isinstance(apps_val, dict):
            apps_section = cast(Dict[str, Any], apps_val)

    for app in app_roles:
        if apps_section_typed is not None:
            entry_typed = apps_section_typed.get(app)
            if entry_typed is None:
                continue
            preflight_vars = entry_typed.preflight_vars
        else:
            entry_obj = apps_section.get(app)
            if not isinstance(entry_obj, dict):
                continue
            entry_map = cast(Dict[str, Any], entry_obj)
            preflight_vars_obj = entry_map.get("preflight_vars", {})
            preflight_vars = (
                cast(Dict[str, Any], preflight_vars_obj)
                if isinstance(preflight_vars_obj, dict)
                else {}
            )

        defaults_path = apps_dir / app / "defaults" / "main.yml"
        if not defaults_path.is_file():
            continue

        defaults_loaded = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
        defaults: Dict[str, Any] = (
            cast(Dict[str, Any], defaults_loaded) if isinstance(defaults_loaded, dict) else {}
        )

        for key in set(preflight_vars.keys()) & set(defaults.keys()):
            role_default = defaults.get(key)
            registry_default = None
            var_spec = preflight_vars.get(key)
            if isinstance(var_spec, PreflightVarSpec):
                registry_default = var_spec.default
            elif isinstance(var_spec, dict):
                spec_map = cast(Dict[str, Any], var_spec)
                registry_default = spec_map.get("default")

            if role_default is not None and registry_default is not None:
                if str(role_default) != str(registry_default):
                    failures.append(
                        f"Registry/role defaults conflict for app '{app}', var '{key}': "
                        f"registry default {registry_default!r} != role default {role_default!r}"
                    )


def check_policy_contract_integrity(policy_registry_path: Path, failures: List[str]) -> None:
    """Validate that policy controls reference real enforcement artifacts.

    Controls of the form `semgrep:<rule-id>` must map to a rule in a discovered
    `.semgrep.yml`. Controls of the form `repo-policy:<kebab-name>` must map to a
    `check_<kebab_name>` function in `linux_hi.policy_utils`. Controls of the form
    `make:<target>` must exist in a discovered `Makefile`.
    """
    if not policy_registry_path.is_file():
        failures.append(f"Missing policy registry file: {policy_registry_path}")
        return

    loaded = yaml.safe_load(policy_registry_path.read_text(encoding="utf-8"))
    try:
        reg = PolicyRegistry.model_validate(loaded or {})
    except ValidationError:
        msg = f"Invalid policy registry format in {policy_registry_path}: 'policies' must be a list"
        failures.append(msg)
        return

    # Discover companion files: look in the policy registry dir and its parent
    base_dirs = [policy_registry_path.parent, policy_registry_path.parent.parent]

    semgrep_ids: set[str] = set()
    semgrep_found = False
    for d in base_dirs:
        candidate = d / ".semgrep.yml"
        if candidate.is_file():
            semgrep_found = True
            semgrep_text = candidate.read_text(encoding="utf-8")
            # Fallback: extract rule ids with a regex to avoid complex typed YAML shapes
            for m in re.finditer(r"(?m)^\s*-\s*id\s*:\s*([^\s#]+)", semgrep_text):
                semgrep_ids.add(m.group(1).strip())
            break

    makefile_text = ""
    makefile_found = False
    for d in base_dirs:
        candidate = d / "Makefile"
        if candidate.is_file():
            makefile_found = True
            makefile_text = candidate.read_text(encoding="utf-8")
            break

    # Import this module to check for repo-policy function targets
    try:
        import importlib

        mod = importlib.import_module("linux_hi.policy_utils")
    except Exception:
        mod = None

    for policy in reg.policies:
        controls = policy.controls
        for control in controls:
            if control.startswith("semgrep:"):
                _, val = control.split(":", 1)
                if val == ".semgrep.yml":
                    if not semgrep_found:
                        failures.append(
                            f"Policy control {control} references .semgrep.yml but none was found"
                        )
                    continue
                if val not in semgrep_ids:
                    failures.append(
                        f"Policy control {control} references unknown semgrep rule '{val}'"
                    )
            elif control.startswith("repo-policy:"):
                _, val = control.split(":", 1)
                fn = "check_" + val.replace("-", "_")
                exported = getattr(mod, "__all__", ()) if mod is not None else ()
                if fn not in exported:
                    failures.append(
                        f"Policy control {control} references missing function '{fn}' "
                        "in linux_hi.policy_utils.__all__"
                    )
            elif control.startswith("make:"):
                _, val = control.split(":", 1)
                if not makefile_found:
                    failures.append(
                        f"Policy control {control} references make target '{val}' "
                        "but no Makefile was found"
                    )
                    continue

                pattern1 = re.search(rf"(^|\n){re.escape(val)}\s*:", makefile_text)
                pattern2 = re.search(rf"\.PHONY:.*\b{re.escape(val)}\b", makefile_text)
                if pattern1 is None and pattern2 is None:
                    failures.append(
                        f"Policy control {control} references missing Make target '{val}'"
                    )
            else:
                failures.append(f"Policy control {control} uses unknown control scheme")


def check_site_become_password_assertion(site_playbook_path: Path, failures: List[str]) -> None:
    """Ensure ansible/site.yml asserts become_passwords for the current host."""
    if not site_playbook_path.is_file():
        failures.append(f"Missing site playbook: {site_playbook_path}")
        return

    loaded = yaml.safe_load(site_playbook_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        failures.append(f"{site_playbook_path} must define a play list")
        return

    plays = cast(List[object], loaded)
    for play_obj in plays:
        if not isinstance(play_obj, dict):
            continue
        play = cast(Dict[str, Any], play_obj)
        pre_tasks_obj = play.get("pre_tasks", [])
        if not isinstance(pre_tasks_obj, list):
            continue
        pre_tasks = cast(List[object], pre_tasks_obj)
        for task_obj in pre_tasks:
            if not isinstance(task_obj, dict):
                continue
            task = cast(Dict[str, Any], task_obj)
            assert_task_obj = task.get("ansible.builtin.assert", task.get("assert"))
            if not isinstance(assert_task_obj, dict):
                continue
            task_text = yaml.safe_dump(task, sort_keys=False)
            if "become_passwords" not in task_text:
                continue
            tags_obj = task.get("tags", [])
            if isinstance(tags_obj, str):
                tags = [tags_obj]
            elif isinstance(tags_obj, list):
                tags = [str(tag) for tag in cast(List[object], tags_obj)]
            else:
                tags = []
            if "always" not in tags:
                failures.append(
                    f"{site_playbook_path} assert task verifying "
                    "become_passwords must be tagged 'always'"
                )
            return

    failures.append(
        f"{site_playbook_path} missing a pre_tasks assert that verifies "
        "become_passwords for inventory_hostname"
    )


def check_app_playbooks(app_roles: List[str], apps_dir: Path, failures: List[str]) -> None:
    """Ensure every registered app has a generated per-app playbook."""
    for app in app_roles:
        playbook = apps_dir / app / "playbook.yml"
        if not playbook.is_file():
            failures.append(
                f"App '{app}' missing per-app playbook: {playbook} "
                "(run 'make generate-apps' to regenerate)"
            )


def check_app_data_paths(app_roles: List[str], registry_path: Path, failures: List[str]) -> None:
    """Ensure persistent apps declare explicit data paths in registry preflight vars."""
    if not registry_path.is_file():
        failures.append(f"Missing registry file: {registry_path}")
        return
    loaded = yaml.safe_load(registry_path.read_text(encoding="utf-8"))

    apps_section: Dict[str, Any] = {}
    apps_typed: dict[str, AppRegistryEntry] | None = None
    try:
        reg_typed: AppRegistry = AppRegistry.model_validate(loaded or {})
        apps_typed = reg_typed.apps
    except ValidationError:
        data = cast(Dict[str, Any], loaded) if isinstance(loaded, dict) else {}
        apps_obj = data.get("apps", {})
        if isinstance(apps_obj, dict):
            apps_section = cast(Dict[str, Any], apps_obj)

    for app in app_roles:
        if apps_typed is not None:
            entry_obj = apps_typed.get(app)
        else:
            entry_obj = apps_section.get(app)

        if isinstance(entry_obj, AppRegistryEntry):
            requires_declared_path = (
                entry_obj.service_type == "containerized"
                or bool(entry_obj.backup)
                or bool(entry_obj.restore)
            )
            if not requires_declared_path:
                continue
            preflight_vars = entry_obj.preflight_vars
        elif isinstance(entry_obj, dict):
            entry_map = cast(Dict[str, Any], entry_obj)
            requires_declared_path = (
                entry_map.get("service_type") == "containerized"
                or bool(entry_map.get("backup", False))
                or bool(entry_map.get("restore", False))
            )
            if not requires_declared_path:
                continue
            preflight_vars_obj = entry_map.get("preflight_vars", {})
            preflight_vars = (
                cast(Dict[str, Any], preflight_vars_obj)
                if isinstance(preflight_vars_obj, dict)
                else {}
            )
        else:
            continue

        if not preflight_vars:
            failures.append(
                f"App '{app}' requires persistence but declares no preflight_vars for data paths"
            )
            continue

        if not any("data_path" in key for key in preflight_vars):
            failures.append(
                f"App '{app}' requires persistence but has no explicit '*_data_path' preflight var"
            )


def check_makefile_guard_checks(makefile_path: Path, failures: List[str]) -> None:
    """Ensure runtime Make variables are guarded with explicit fast-fail checks."""
    if not makefile_path.is_file():
        failures.append(f"Missing Makefile: {makefile_path}")
        return

    text = makefile_path.read_text(encoding="utf-8")
    for var_name in ("APP", "SVC"):
        if f"$({var_name})" not in text:
            continue
        has_nonempty_guard = re.search(rf'test -n "\$\({var_name}\)"', text) is not None
        has_error_message = re.search(rf"Error: {var_name}\b", text) is not None
        if not (has_nonempty_guard and has_error_message):
            failures.append(
                f"Makefile references $({var_name}) but must fail fast "
                "with an explicit guard check and error message"
            )


def check_no_direct_host_group_writes(root: Path, failures: List[str]) -> None:
    """Detect direct writes to host_vars/group_vars outside the dedicated seams."""
    allowed_files = {
        root / "models" / "ansible" / "access.py",
        root / "linux_hi" / "vault" / "service.py",
    }

    path_markers = ("host_vars", "group_vars", "ansible/group_vars", "ansible/inventory")
    write_markers = ("write_text(", "write_bytes(", ".write(")
    skip_dirs = {root / "tests", root / ".venv"}

    for py_file in sorted(root.rglob("*.py")):
        if py_file in allowed_files:
            continue
        if any(py_file.is_relative_to(d) for d in skip_dirs):
            continue
        text = py_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not any(marker in line for marker in path_markers):
                continue
            if any(marker in line for marker in write_markers):
                failures.append(
                    f"Direct write to Ansible state detected in {py_file}:{line_no}; "
                    "use models/ansible/access.py or linux_hi/vault/service.py"
                )


def check_makefile_phony_and_style(
    makefile_path: Path, app_roles: List[str], failures: List[str]
) -> None:
    """Validate public .PHONY targets, help visibility, and kebab-case style."""
    if not makefile_path.is_file():
        failures.append(f"Missing Makefile: {makefile_path}")
        return

    text = makefile_path.read_text(encoding="utf-8")
    phony_targets: list[str] = []
    for ln in text.splitlines():
        stripped = ln.lstrip()
        if stripped.startswith(".PHONY:"):
            rest = stripped[len(".PHONY:") :].strip()
            phony_targets.extend(token for token in rest.split() if token)

    if not phony_targets:
        failures.append("Makefile missing .PHONY declarations for public targets")
        return

    help_lines = [ln for ln in text.splitlines() if "@echo" in ln]
    for target in phony_targets:
        if target.startswith("_") or "$(" in target:
            continue
        if not re.fullmatch(r"[a-z0-9-]+", target):
            failures.append(f"Public target '{target}' should use lowercase kebab-case")

        # If the target is annotated as an app role and the help contains
        # an app meta entry, consider it covered.
        if target in app_roles and any(re.search(r"<app", ln) for ln in help_lines):
            continue

        if not any(re.search(rf"\b{re.escape(target)}\b", ln) for ln in help_lines):
            failures.append(f"Public target '{target}' must appear in make help output")


class PolicyRunner:
    """Coordinates all repository policy checks against a fixed project root."""

    def __init__(self, root: Path) -> None:
        """Derive all check paths from the repository root."""
        self._root = root
        self._apps_dir = root / "ansible" / "apps"
        self._registry = root / "ansible" / "registry.yml"
        self._tests_dir = root / "tests"
        self._e2e_dir = root / "tests" / "e2e"
        self._policy_contract = root / "docs" / "POLICY_CONTRACT.yml"
        self._makefile = root / "Makefile"
        self._ansible_dir = root / "ansible"
        self._setup_playbook = root / "ansible" / "setup.yml"

    def run(self) -> None:
        """Run all checks and exit non-zero if any fail."""
        failures: list[str] = []
        app_roles = get_app_roles(self._apps_dir)
        check_registry_entries(app_roles, self._registry, failures)
        check_app_dirs(app_roles, self._apps_dir, failures, self._registry)
        check_registry_conflicts(app_roles, self._apps_dir, self._registry, failures)
        check_app_tests(app_roles, self._tests_dir, self._e2e_dir, failures)
        check_playbook_vars(self._ansible_dir, failures)
        check_site_become_password_assertion(self._setup_playbook, failures)
        check_app_playbooks(app_roles, self._apps_dir, failures)
        check_app_data_paths(app_roles, self._registry, failures)
        check_policy_registry_controls(self._policy_contract, failures)
        check_policy_contract_integrity(self._policy_contract, failures)
        check_makefile_host_selector(self._makefile, failures)
        check_makefile_guard_checks(self._makefile, failures)
        check_makefile_phony_and_style(self._makefile, app_roles, failures)
        check_no_direct_host_group_writes(self._root, failures)
        if failures:
            print("\nREPO POLICY CHECK FAILED:")
            for fail in failures:
                print(f"- {fail}")
            sys.exit(1)
        print("All repo policy checks passed.")


__all__ = [
    "PolicyRunner",
    "check_app_data_paths",
    "check_app_dirs",
    "check_app_playbooks",
    "check_app_tests",
    "check_makefile_guard_checks",
    "check_makefile_host_selector",
    "check_makefile_phony_and_style",
    "check_no_direct_host_group_writes",
    "check_playbook_vars",
    "check_policy_contract_integrity",
    "check_policy_registry_controls",
    "check_registry_conflicts",
    "check_registry_entries",
    "check_site_become_password_assertion",
    "get_app_roles",
]
