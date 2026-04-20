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
