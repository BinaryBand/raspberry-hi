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
        "restic",
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
    assert entry.restore is True
    assert entry.cleanup is True
    assert entry.dependencies == ["postgres"]


def test_containerized_apps_declare_backup_and_restore() -> None:
    """Each containerized app must implement backup and restore handlers."""
    for app in ANSIBLE_DATA.containerized_apps():
        assert (ANSIBLE_DIR / "apps" / app / "backup.yml").exists()
        assert (ANSIBLE_DIR / "apps" / app / "restore.yml").exists()


def test_containerized_app_backups_delegate_to_restic() -> None:
    """Each app backup task should hand off snapshotting to the restic role."""
    for app in ANSIBLE_DATA.containerized_apps():
        content = _read_text(f"ansible/apps/{app}/backup.yml")
        assert "name: restic" in content


def test_containerized_app_backups_validate_snapshot_paths() -> None:
    """Each app backup task should verify snapshot source paths before restic runs."""
    for app in ANSIBLE_DATA.containerized_apps():
        content = _read_text(f"ansible/apps/{app}/backup.yml")
        assert "ansible.builtin.stat" in content
        assert "ansible.builtin.fail" in content


def test_restic_operational_tasks_prepare_their_own_prerequisites() -> None:
    """Direct restic entry points must bootstrap their own client and repo checks."""
    for task_name in ["backup", "prune", "restore"]:
        content = _read_text(f"ansible/apps/restic/tasks/{task_name}.yml")
        assert "import_tasks: prepare.yml" in content
        assert "import_tasks: repository.yml" in content


def test_minio_bucket_setup_fails_when_health_poll_never_succeeds() -> None:
    """MinIO bucket setup must stop before mc commands if readiness polling never succeeds."""
    content = _read_text("ansible/apps/minio/tasks/setup_mc_bucket.yml")
    assert "Wait until MinIO health endpoint responds HTTP 200" in content
    assert "Fail if MinIO health endpoint never became ready" in content


def test_postgres_backup_and_restore_share_readiness_check() -> None:
    """PostgreSQL lifecycle flows should reuse the shared readiness gate."""
    backup_content = _read_text("ansible/apps/postgres/backup.yml")
    restore_content = _read_text("ansible/apps/postgres/restore.yml")
    wait_ready_content = _read_text("ansible/apps/postgres/tasks/wait_ready.yml")

    assert "include_tasks: tasks/wait_ready.yml" in backup_content
    assert "include_tasks: tasks/wait_ready.yml" in restore_content
    assert "Wait for PostgreSQL to accept connections" in wait_ready_content
    assert "Fail if PostgreSQL never became ready" in wait_ready_content


def test_restore_and_cleanup_playbooks_use_registry_for_supported_apps() -> None:
    """Restore and cleanup playbooks should derive supported apps from registry metadata."""
    cleanup_content = _read_text("ansible/playbooks/cleanup.yml")
    restore_content = _read_text("ansible/playbooks/restore.yml")

    assert 'file: "{{ playbook_dir }}/../registry.yml"' in cleanup_content
    assert "cleanup_app in cleanup_supported_apps" in cleanup_content
    assert 'file: "{{ playbook_dir }}/../apps/{{ cleanup_app }}/cleanup.yml"' in cleanup_content
    assert "['minio', 'postgres', 'baikal']" not in cleanup_content

    assert 'file: "{{ playbook_dir }}/../registry.yml"' in restore_content
    assert "restore_app in restore_supported_apps" in restore_content
    assert 'file: "{{ playbook_dir }}/../apps/{{ restore_app }}/restore.yml"' in restore_content
    assert "['minio', 'postgres', 'baikal']" not in restore_content


def test_app_restart_handlers_delegate_to_service_adapter() -> None:
    """App restart handlers should call the shared service_adapter restart task."""
    for app in ANSIBLE_DATA.containerized_apps():
        content = _read_text(f"ansible/apps/{app}/handlers/main.yml")
        assert (
            "ansible.builtin.include_tasks:" in content
            or "ansible.builtin.import_tasks:" in content
        )
        assert "../../../roles/service_adapter/tasks/restart.yml" in content


def test_generated_playbooks_have_named_import_playbook_items() -> None:
    """Every import_playbook item must have a name: to satisfy ansible-lint name[play]."""
    for app in ANSIBLE_DATA.all_apps():
        lines = (ANSIBLE_DIR / "apps" / app / "playbook.yml").read_text().splitlines()
        for i, line in enumerate(lines):
            if "import_playbook:" in line:
                preceding = lines[i - 1].strip().lstrip("- ") if i > 0 else ""
                assert preceding.startswith("name:"), (
                    f"ansible/apps/{app}/playbook.yml: import_playbook at line {i + 1} "
                    "has no name: (run 'make generate-apps' to regenerate)"
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
                f"ansible/apps/{app}/playbook.yml is missing import for dependency '{dep}' "
                "(run 'make generate-apps' to regenerate)"
            )


def test_containerized_apps_use_service_adapter_prepare_for_quadlet_path() -> None:
    """Container apps should delegate quadlet directory creation to service_adapter."""
    for app in ANSIBLE_DATA.containerized_apps():
        content = _read_text(f"ansible/apps/{app}/tasks/main.yml")
        assert "tasks_from: prepare" in content
        assert "Ensure Podman quadlet directory exists" not in content
