"""Contract tests for registry-backed Ansible app wiring."""

from __future__ import annotations

from pathlib import Path

from models import ANSIBLE_DATA

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE_DIR = ROOT / "ansible"


def _read_text(relative_path: str) -> str:
    """Return repository file contents."""
    return (ROOT / relative_path).read_text()


def test_registry_has_expected_keys() -> None:
    """The registry remains the single source of truth for known apps."""
    assert ANSIBLE_DATA.all_apps() == [
        "minio",
        "postgres",
        "baikal",
        "synapse",
        "mautrix-whatsapp",
    ]


def test_containerized_apps_subset() -> None:
    """Only long-running container apps are classified as containerized."""
    assert ANSIBLE_DATA.containerized_apps() == [
        "minio",
        "postgres",
        "baikal",
        "synapse",
        "mautrix-whatsapp",
    ]


def test_app_entry_data() -> None:
    """Registry entries expose lifecycle and dependency metadata."""
    entry = ANSIBLE_DATA.get_app_entry("baikal")
    assert entry.service_type == "containerized"
    assert entry.dependencies == ["postgres"]


def test_minio_bucket_setup_fails_when_health_poll_never_succeeds() -> None:
    """MinIO bucket setup must stop before mc commands if readiness polling never succeeds."""
    content = _read_text("ansible/apps/minio/tasks/setup_mc_bucket.yml")
    assert "Wait until MinIO health endpoint responds HTTP 200" in content
    assert "Fail if MinIO health endpoint never became ready" in content


def test_app_restart_handlers_delegate_to_service_adapter() -> None:
    """App restart handlers should call the shared service_adapter restart task."""
    for app in ANSIBLE_DATA.containerized_apps():
        content = _read_text(f"ansible/apps/{app}/handlers/main.yml")
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
        content = _read_text(f"ansible/apps/{app}/tasks/main.yml")
        assert "tasks_from: prepare" in content
        assert "Ensure Podman quadlet directory exists" not in content
