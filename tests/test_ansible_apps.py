"""Contract tests for registry-backed Ansible app wiring."""

from __future__ import annotations

from pathlib import Path

from scripts.utils.ansible_utils import all_apps, containerized_apps, get_app_entry

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE_DIR = ROOT / "ansible"


def _read_text(relative_path: str) -> str:
    """Return repository file contents."""
    return (ROOT / relative_path).read_text()


def test_registry_has_expected_keys() -> None:
    """The registry remains the single source of truth for known apps."""
    assert all_apps() == ["minio", "postgres", "baikal", "restic"]


def test_containerized_apps_subset() -> None:
    """Only long-running container apps are classified as containerized."""
    assert containerized_apps() == ["minio", "postgres", "baikal"]


def test_app_entry_data() -> None:
    """Registry entries expose lifecycle and dependency metadata."""
    entry = get_app_entry("baikal")
    assert entry.service_type == "containerized"
    assert entry.restore is True
    assert entry.cleanup is True
    assert entry.dependencies == ["postgres"]


def test_containerized_apps_declare_backup_and_restore() -> None:
    """Each containerized app must implement backup and restore handlers."""
    for app in containerized_apps():
        assert (ANSIBLE_DIR / "apps" / app / "backup" / "main.yml").exists()
        assert (ANSIBLE_DIR / "apps" / app / "restore" / "main.yml").exists()


def test_containerized_app_backups_delegate_to_restic() -> None:
    """Each app backup task should hand off snapshotting to the restic role."""
    for app in containerized_apps():
        content = _read_text(f"ansible/apps/{app}/backup/main.yml")
        assert "name: restic" in content


def test_containerized_app_backups_validate_snapshot_paths() -> None:
    """Each app backup task should verify snapshot source paths before restic runs."""
    for app in containerized_apps():
        content = _read_text(f"ansible/apps/{app}/backup/main.yml")
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
    backup_content = _read_text("ansible/apps/postgres/backup/main.yml")
    restore_content = _read_text("ansible/apps/postgres/restore/main.yml")
    wait_ready_content = _read_text("ansible/apps/postgres/tasks/wait_ready.yml")

    assert (
        'include_tasks: "{{ playbook_dir }}/apps/postgres/tasks/wait_ready.yml"' in backup_content
    )
    assert (
        'include_tasks: "{{ playbook_dir }}/apps/postgres/tasks/wait_ready.yml"' in restore_content
    )
    assert "Wait for PostgreSQL to accept connections" in wait_ready_content
    assert "Fail if PostgreSQL never became ready" in wait_ready_content
