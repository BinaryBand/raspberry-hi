"""Policy checks for POLICY_CONTRACT.yml integrity and control references."""

from __future__ import annotations

import importlib
import re
import types
from pathlib import Path

from ._loader import Failures, _load_policy_registry


def _discover_semgrep_ids(base_dirs: list[Path]) -> tuple[set[str], bool]:
    """Return (rule_ids, found) by scanning base_dirs for the first rules/ directory."""
    for d in base_dirs:
        rules_dir = d / "rules"
        if rules_dir.is_dir():
            ids: set[str] = set()
            for rule_file in sorted(rules_dir.glob("*.yml")):
                ids.update(
                    m.group(1).strip()
                    for m in re.finditer(
                        r"(?m)^\s*-\s*id\s*:\s*([^\s#]+)",
                        rule_file.read_text(encoding="utf-8"),
                    )
                )
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
    if val == "rules/":
        if not semgrep_found:
            failures.append(
                f"Policy control {control} references rules/ but no rules/ directory was found"
            )
        return
    if val not in semgrep_ids:
        failures.append(f"Policy control {control} references unknown semgrep rule '{val}'")


def _check_repo_policy_control(control: str, val: str, mod: object, failures: Failures) -> None:
    fn = "check_" + val.replace("-", "_")
    exported = getattr(mod, "__all__", ()) if mod is not None else ()
    if fn not in exported:
        failures.append(
            f"Policy control {control} references missing function '{fn}' "
            "in linux_hi.policy.__all__"
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


def check_policy_contract_integrity(policy_registry_path: Path, failures: Failures) -> None:
    """Validate that policy controls reference real enforcement artifacts."""
    reg = _load_policy_registry(policy_registry_path, failures)
    if reg is None:
        return

    base_dirs = [policy_registry_path.parent, policy_registry_path.parent.parent]
    semgrep_ids, semgrep_found = _discover_semgrep_ids(base_dirs)
    makefile_text, makefile_found = _discover_makefile_text(base_dirs)

    mod: types.ModuleType | None
    try:
        mod = importlib.import_module("linux_hi.policy")
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
