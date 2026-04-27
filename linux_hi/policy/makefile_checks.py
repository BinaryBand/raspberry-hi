"""Policy checks for Makefile conventions and style."""

from __future__ import annotations

import re
from pathlib import Path

from ._loader import Failures


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
