"""Unit tests for policy app checks."""

from __future__ import annotations

from pathlib import Path

from linux_hi.policy import app_checks


def test_get_app_roles_returns_only_directories(tmp_path: Path) -> None:
    """App role discovery should include directory names and ignore regular files."""
    (tmp_path / "synapse").mkdir()
    (tmp_path / "postgres").mkdir()
    (tmp_path / "README.txt").write_text("not a role", encoding="utf-8")

    roles = sorted(app_checks.get_app_roles(tmp_path))

    assert roles == ["postgres", "synapse"]


def test_check_registry_entries_reports_missing_registry(tmp_path: Path) -> None:
    """Registry entry checks should fail when registry file is absent."""
    failures: list[str] = []

    app_checks.check_registry_entries(["synapse"], tmp_path / "registry.yml", failures)

    assert failures and "Missing registry file" in failures[0]


def test_check_registry_entries_reports_unregistered_app(tmp_path: Path) -> None:
    """Registry entry checks should flag app roles absent from registry.yml."""
    registry = tmp_path / "registry.yml"
    registry.write_text("apps:\n  postgres:\n    service_type: containerized\n", encoding="utf-8")

    failures: list[str] = []
    app_checks.check_registry_entries(["postgres", "synapse"], registry, failures)

    assert any(
        "synapse" in failure and "missing from registry.yml" in failure for failure in failures
    )


def test_check_app_dirs_reports_missing_tasks_dir(tmp_path: Path) -> None:
    """App directory checks should require a tasks subdirectory per app role."""
    apps_dir = tmp_path
    (apps_dir / "synapse").mkdir()

    failures: list[str] = []
    app_checks.check_app_dirs(["synapse"], apps_dir, failures)

    assert failures == ["App 'synapse' missing 'tasks/' directory"]


def test_check_app_tests_uses_framework_coverage_marker(tmp_path: Path) -> None:
    """Framework-loop marker should satisfy app test coverage requirements."""
    tests_dir = tmp_path / "tests"
    unit_dir = tests_dir / "unit"
    e2e_dir = tests_dir / "e2e"
    unit_dir.mkdir(parents=True)
    e2e_dir.mkdir(parents=True)

    (unit_dir / "test_ansible_apps.py").write_text(
        "for app in ANSIBLE_DATA.all_apps():\n    pass\n",
        encoding="utf-8",
    )

    failures: list[str] = []
    app_checks.check_app_tests(["synapse", "postgres"], tests_dir, e2e_dir, failures)

    assert failures == []


def test_check_app_tests_reports_missing_coverage(tmp_path: Path) -> None:
    """App test checks should report roles without framework, e2e, or app-specific mentions."""
    tests_dir = tmp_path / "tests"
    unit_dir = tests_dir / "unit"
    e2e_dir = tests_dir / "e2e"
    unit_dir.mkdir(parents=True)
    e2e_dir.mkdir(parents=True)

    (unit_dir / "test_ansible_apps.py").write_text("# no app mentions\n", encoding="utf-8")

    failures: list[str] = []
    app_checks.check_app_tests(["synapse"], tests_dir, e2e_dir, failures)

    assert failures and "missing framework coverage" in failures[0]


def test_check_registry_conflicts_reports_missing_registry(tmp_path: Path) -> None:
    """Registry conflict checks should fail when registry file is missing."""
    failures: list[str] = []

    app_checks.check_registry_conflicts(
        ["synapse"],
        tmp_path / "apps",
        tmp_path / "registry.yml",
        failures,
    )

    assert failures and "Missing registry file" in failures[0]


def test_check_app_playbooks_reports_missing_playbook(tmp_path: Path) -> None:
    """Playbook checks should require a per-app playbook.yml file."""
    apps_dir = tmp_path / "apps"
    (apps_dir / "synapse").mkdir(parents=True)

    failures: list[str] = []
    app_checks.check_app_playbooks(["synapse"], apps_dir, failures)

    assert failures and "missing per-app playbook" in failures[0]
