"""Policy checks for Ansible playbooks and inventory conventions."""

from __future__ import annotations

from pathlib import Path

import yaml

from ._loader import Failures, _as_dict, _as_list, _load_yaml


def check_playbook_vars(ansible_dir: Path, failures: Failures) -> None:
    """Verify that root-level playbooks do not define top-level vars blocks."""
    for path in sorted(ansible_dir.glob("*.yml")) + sorted(ansible_dir.glob("*.yaml")):
        if path.name == "registry.yml":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("  vars:"):
                failures.append(
                    f"Playbook vars block in {path}:{line_no} "
                    "(variables are only allowed in group_vars/host_vars)"
                )


def _find_become_assertion(tasks: list, source: Path, failures: Failures) -> bool:
    """Scan a task list for a become_passwords assert tagged 'always'.

    Returns True if found (appending a failure if tagged incorrectly), False if absent.
    """
    for task_obj in tasks:
        task = _as_dict(task_obj)
        if task is None:
            continue
        if _as_dict(task.get("ansible.builtin.assert", task.get("assert"))) is None:
            continue
        if "become_passwords" not in yaml.safe_dump(task, sort_keys=False):
            continue
        tags_obj = task.get("tags", [])
        tags = (
            [tags_obj]
            if isinstance(tags_obj, str)
            else [str(t) for t in (_as_list(tags_obj) or [])]
        )
        if "always" not in tags:
            failures.append(
                f"{source} assert task verifying become_passwords must be tagged 'always'"
            )
        return True
    return False


def _check_pre_tasks_file(pre_tasks_path: Path, failures: Failures) -> None:
    """Verify pre_tasks.yml contains the become_passwords assertion tagged 'always'."""
    if not pre_tasks_path.is_file():
        failures.append(f"Missing shared pre_tasks file: {pre_tasks_path}")
        return
    tasks = _as_list(_load_yaml(pre_tasks_path))
    if tasks is None:
        failures.append(f"{pre_tasks_path} must define a task list")
        return
    if not _find_become_assertion(tasks, pre_tasks_path, failures):
        failures.append(
            f"{pre_tasks_path} missing an assert that verifies "
            "become_passwords for inventory_hostname"
        )


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
            # import_tasks delegation — verify the assertion lives in pre_tasks.yml
            import_ref = task.get("ansible.builtin.import_tasks") or task.get("import_tasks")
            if isinstance(import_ref, str) and "pre_tasks.yml" in import_ref:
                # Look for pre_tasks.yml in the tasks directory relative to the playbook
                _check_pre_tasks_file(
                    (site_playbook_path.parent.parent / "tasks" / "pre_tasks.yml").resolve(),
                    failures,
                )
                return
        # Inline assert scan
        if _find_become_assertion(list(pre_tasks), site_playbook_path, failures):
            return

    failures.append(
        f"{site_playbook_path} missing a pre_tasks assert that verifies "
        "become_passwords for inventory_hostname"
    )


def check_no_direct_host_group_writes(root: Path, failures: Failures) -> None:
    """Detect direct writes to host_vars/group_vars outside the dedicated seams."""
    allowed_files = {
        root / "linux_hi" / "models" / "ansible" / "access.py",
        root / "linux_hi" / "services" / "vault.py",
        root / "linux_hi" / "cli" / "generate_apps.py",
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
                    "use linux_hi/models/ansible/access.py or linux_hi/services/vault.py"
                )
