"""Contract tests for registry-backed Ansible app wiring."""

from __future__ import annotations

from pathlib import Path

from linux_hi.models import ANSIBLE_DATA

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "ansible"


def test_registry_has_expected_keys() -> None:
    """The registry exposes at least one unique app key."""
    apps = ANSIBLE_DATA.all_apps()
    assert apps
    assert len(apps) == len(set(apps))


def test_containerized_apps_subset() -> None:
    """Containerized app classification should be a subset of registered apps."""
    all_apps = set(ANSIBLE_DATA.all_apps())
    containerized = ANSIBLE_DATA.containerized_apps()
    assert containerized
    assert set(containerized).issubset(all_apps)


def test_registry_entries_have_known_service_type() -> None:
    """Each registry entry should expose a valid service type."""
    for app in ANSIBLE_DATA.all_apps():
        entry = ANSIBLE_DATA.get_app_entry(app)
        assert entry.service_type == "containerized"


def test_app_entry_data() -> None:
    """Dependency declarations should reference registered app keys."""
    all_apps = set(ANSIBLE_DATA.all_apps())
    apps_with_deps = [
        app for app in ANSIBLE_DATA.all_apps() if ANSIBLE_DATA.get_app_entry(app).dependencies
    ]
    if not apps_with_deps:
        return

    for app in apps_with_deps:
        deps = ANSIBLE_DATA.get_app_entry(app).dependencies
        assert deps
        for dep in deps:
            assert dep in all_apps


def test_app_restart_handlers_delegate_to_service_adapter() -> None:
    """App restart handlers should call the shared service_adapter restart task."""
    for app in ANSIBLE_DATA.containerized_apps():
        content = (ROOT / f"ansible/apps/{app}/handlers/main.yml").read_text()
        assert (
            "ansible.builtin.include_tasks:" in content
            or "ansible.builtin.import_tasks:" in content
        )
        assert "../../../roles/service_adapter/tasks/restart.yml" in content


def test_playbooks_have_named_import_playbook_items() -> None:
    """Every import_playbook item must have a name: to satisfy ansible-lint name[play]."""
    for app in ANSIBLE_DATA.all_apps():
        lines = (ANSIBLE_DIR / "apps" / app / "playbook.yml").read_text().splitlines()
        for i, line in enumerate(lines):
            if "import_playbook:" in line:
                preceding = lines[i - 1].strip().lstrip("- ") if i > 0 else ""
                assert preceding.startswith("name:"), (
                    f"ansible/apps/{app}/playbook.yml: import_playbook at line {i + 1} has no name:"
                )


def test_apps_with_dependencies_import_dependency_playbooks() -> None:
    """Apps that declare dependencies must import the dependency playbook."""
    for app in ANSIBLE_DATA.all_apps():
        entry = ANSIBLE_DATA.get_app_entry(app)
        if not entry.dependencies:
            continue
        content = (ANSIBLE_DIR / "apps" / app / "playbook.yml").read_text()
        for dep in entry.dependencies:
            assert f"import_playbook: ../{dep}/playbook.yml" in content, (
                f"ansible/apps/{app}/playbook.yml is missing import for dependency '{dep}'"
            )


def test_containerized_apps_use_service_adapter_prepare_for_quadlet_path() -> None:
    """Container apps should delegate quadlet directory creation to service_adapter."""
    for app in ANSIBLE_DATA.containerized_apps():
        content = (ROOT / f"ansible/apps/{app}/tasks/main.yml").read_text()
        assert "tasks_from: prepare" in content
        assert "Ensure Podman quadlet directory exists" not in content
