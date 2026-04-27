"""Utilities for repository policy checks."""

from __future__ import annotations

import importlib
import re
import sys
import types
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from models.ansible.registry import AppRegistry, AppRegistryEntry
from models.policy import PolicyRegistry

Failures = list[str]


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


def _load_yaml(path: Path) -> object:
    """Load a YAML file and return the raw parsed object."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _as_dict(obj: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], obj) if isinstance(obj, dict) else None


def _as_list(obj: object) -> list[object] | None:
    return cast(list[object], obj) if isinstance(obj, list) else None


def _load_registry(registry_path: Path) -> dict[str, AppRegistryEntry]:
    """Load and validate the app registry, returning a mapping of app name to entry.

    Raises ValidationError if the file content does not conform to AppRegistry.
    """
    return AppRegistry.model_validate(_load_yaml(registry_path) or {}).apps


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
    """Check that each application role has required subdirectories.

    If a registry path is provided, backup/restore requirements are derived from
    each app's lifecycle flags. Otherwise, backup/restore/tasks are required.
    """
    registry: dict[str, AppRegistryEntry] | None = None
    if registry_path and registry_path.exists():
        registry = _load_registry(registry_path)

    for app in app_roles:
        app_path = apps_dir / app
        required_dirs = ["tasks"]

        if registry is not None:
            entry = registry.get(app)
            if entry is not None:
                if entry.backup:
                    required_dirs.append("backup")
                if entry.restore:
                    required_dirs.append("restore")
            else:
                required_dirs.extend(["backup", "restore"])
        else:
            required_dirs.extend(["backup", "restore"])

        for subdir in required_dirs:
            if not (app_path / subdir).is_dir():
                failures.append(f"App '{app}' missing '{subdir}/' directory")


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


def check_playbook_vars(ansible_dir: Path, failures: Failures) -> None:
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


def check_policy_registry_controls(policy_registry_path: Path, failures: Failures) -> None:
    """Ensure every enforced policy has at least one explicit control target."""
    reg = _load_policy_registry(policy_registry_path, failures)
    if reg is None:
        return

    for idx, policy in enumerate(reg.policies, start=1):
        policy_id = policy.id or f"policy-{idx}"
        status = (policy.status or "advisory").lower()
        if status != "enforced":
            continue
        if not policy.controls:
            failures.append(f"Policy '{policy_id}' is marked enforced but has no control targets")


def check_makefile_host_selector(makefile_path: Path, failures: Failures) -> None:
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
    app_roles: list[str], apps_dir: Path, registry_path: Path, failures: Failures
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


def _discover_semgrep_ids(base_dirs: list[Path]) -> tuple[set[str], bool]:
    """Return (rule_ids, found) by scanning base_dirs for the first .semgrep.yml."""
    for d in base_dirs:
        candidate = d / ".semgrep.yml"
        if candidate.is_file():
            ids = {
                m.group(1).strip()
                for m in re.finditer(
                    r"(?m)^\s*-\s*id\s*:\s*([^\s#]+)",
                    candidate.read_text(encoding="utf-8"),
                )
            }
            return ids, True
    return set(), False


def _discover_makefile_text(base_dirs: list[Path]) -> tuple[str, bool]:
    """Return (text, found) by scanning base_dirs for the first Makefile."""
    for d in base_dirs:
        candidate = d / "Makefile"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8"), True
    return "", False


def _check_semgrep_control(
    control: str, val: str, semgrep_ids: set[str], semgrep_found: bool, failures: Failures
) -> None:
    if val == ".semgrep.yml":
        if not semgrep_found:
            failures.append(f"Policy control {control} references .semgrep.yml but none was found")
        return
    if val not in semgrep_ids:
        failures.append(f"Policy control {control} references unknown semgrep rule '{val}'")


def _check_repo_policy_control(control: str, val: str, mod: object, failures: Failures) -> None:
    fn = "check_" + val.replace("-", "_")
    exported = getattr(mod, "__all__", ()) if mod is not None else ()
    if fn not in exported:
        failures.append(
            f"Policy control {control} references missing function '{fn}' "
            "in linux_hi.policy_utils.__all__"
        )


def _check_make_control(
    control: str, val: str, makefile_text: str, makefile_found: bool, failures: Failures
) -> None:
    if not makefile_found:
        failures.append(
            f"Policy control {control} references make target '{val}' but no Makefile was found"
        )
        return
    pattern1 = re.search(rf"(^|\n){re.escape(val)}\s*:", makefile_text)
    pattern2 = re.search(rf"\.PHONY:.*\b{re.escape(val)}\b", makefile_text)
    if pattern1 is None and pattern2 is None:
        failures.append(f"Policy control {control} references missing Make target '{val}'")


def check_policy_contract_integrity(policy_registry_path: Path, failures: Failures) -> None:
    """Validate that policy controls reference real enforcement artifacts.

    Controls of the form `semgrep:<rule-id>` must map to a rule in a discovered
    `.semgrep.yml`. Controls of the form `repo-policy:<kebab-name>` must map to a
    `check_<kebab_name>` function in `linux_hi.policy_utils`. Controls of the form
    `make:<target>` must exist in a discovered `Makefile`.
    """
    reg = _load_policy_registry(policy_registry_path, failures)
    if reg is None:
        return

    base_dirs = [policy_registry_path.parent, policy_registry_path.parent.parent]
    semgrep_ids, semgrep_found = _discover_semgrep_ids(base_dirs)
    makefile_text, makefile_found = _discover_makefile_text(base_dirs)

    mod: types.ModuleType | None
    try:
        mod = importlib.import_module("linux_hi.policy_utils")
    except ImportError:
        mod = None

    for policy in reg.policies:
        for control in policy.controls:
            _, val = control.split(":", 1)
            if control.startswith("semgrep:"):
                _check_semgrep_control(control, val, semgrep_ids, semgrep_found, failures)
            elif control.startswith("repo-policy:"):
                _check_repo_policy_control(control, val, mod, failures)
            elif control.startswith("make:"):
                _check_make_control(control, val, makefile_text, makefile_found, failures)
            else:
                failures.append(f"Policy control {control} uses unknown control scheme")


def check_site_become_password_assertion(site_playbook_path: Path, failures: Failures) -> None:
    """Ensure canonical setup playbook asserts become_passwords for the current host."""
    if not site_playbook_path.is_file():
        failures.append(f"Missing site playbook: {site_playbook_path}")
        return

    plays = _as_list(_load_yaml(site_playbook_path))
    if plays is None:
        failures.append(f"{site_playbook_path} must define a play list")
        return

    for play_obj in plays:
        play = _as_dict(play_obj)
        if play is None:
            continue
        pre_tasks = _as_list(play.get("pre_tasks", []))
        if pre_tasks is None:
            continue
        for task_obj in pre_tasks:
            task = _as_dict(task_obj)
            if task is None:
                continue
            if _as_dict(task.get("ansible.builtin.assert", task.get("assert"))) is None:
                continue
            if "become_passwords" not in yaml.safe_dump(task, sort_keys=False):
                continue
            tags_obj = task.get("tags", [])
            if isinstance(tags_obj, str):
                tags = [tags_obj]
            else:
                tags = [str(t) for t in (_as_list(tags_obj) or [])]
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


def check_makefile_guard_checks(makefile_path: Path, failures: Failures) -> None:
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


def check_no_direct_host_group_writes(root: Path, failures: Failures) -> None:
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


def _parse_phony_targets(text: str) -> list[str]:
    """Extract all target names from .PHONY declarations in Makefile text."""
    targets: list[str] = []
    for ln in text.splitlines():
        stripped = ln.lstrip()
        if stripped.startswith(".PHONY:"):
            rest = stripped[len(".PHONY:") :].strip()
            targets.extend(token for token in rest.split() if token)
    return targets


def _check_phony_target(
    target: str, help_lines: list[str], app_roles: list[str], failures: Failures
) -> None:
    """Validate a single public .PHONY target for style and help visibility."""
    if target.startswith("_") or "$(" in target:
        return
    if not re.fullmatch(r"[a-z0-9-]+", target):
        failures.append(f"Public target '{target}' should use lowercase kebab-case")
    # App-role targets are covered if the help output contains a generic <app> entry.
    if target in app_roles and any(re.search(r"<app", ln) for ln in help_lines):
        return
    if not any(re.search(rf"\b{re.escape(target)}\b", ln) for ln in help_lines):
        failures.append(f"Public target '{target}' must appear in make help output")


def check_makefile_phony_and_style(
    makefile_path: Path, app_roles: list[str], failures: Failures
) -> None:
    """Validate public .PHONY targets, help visibility, and kebab-case style."""
    if not makefile_path.is_file():
        failures.append(f"Missing Makefile: {makefile_path}")
        return

    text = makefile_path.read_text(encoding="utf-8")
    phony_targets = _parse_phony_targets(text)
    if not phony_targets:
        failures.append("Makefile missing .PHONY declarations for public targets")
        return

    help_lines = [ln for ln in text.splitlines() if "@echo" in ln]
    for target in phony_targets:
        _check_phony_target(target, help_lines, app_roles, failures)


class PolicyRunner:
    """Coordinates all repository policy checks against a fixed project root."""

    def __init__(self, root: Path) -> None:
        """Store the repository root; all check paths are derived in run()."""
        self._root = root

    def run(self) -> None:
        """Run all checks and exit non-zero if any fail."""
        root = self._root
        ansible_dir = root / "ansible"
        apps_dir = ansible_dir / "apps"
        registry = ansible_dir / "registry.yml"
        policy_contract = root / "docs" / "POLICY_CONTRACT.yml"
        makefile = root / "Makefile"
        failures: Failures = []
        app_roles = get_app_roles(apps_dir)
        check_registry_entries(app_roles, registry, failures)
        check_app_dirs(app_roles, apps_dir, failures, registry)
        check_registry_conflicts(app_roles, apps_dir, registry, failures)
        check_app_tests(app_roles, root / "tests", root / "tests" / "e2e", failures)
        check_playbook_vars(ansible_dir, failures)
        check_site_become_password_assertion(ansible_dir / "playbooks" / "setup.yml", failures)
        check_app_playbooks(app_roles, apps_dir, failures)
        check_app_data_paths(app_roles, registry, failures)
        check_policy_registry_controls(policy_contract, failures)
        check_policy_contract_integrity(policy_contract, failures)
        check_makefile_host_selector(makefile, failures)
        check_makefile_guard_checks(makefile, failures)
        check_makefile_phony_and_style(makefile, app_roles, failures)
        check_no_direct_host_group_writes(root, failures)
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
