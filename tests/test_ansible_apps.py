"""Contract tests for Ansible app wiring that has broken before."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE_DIR = ROOT / "ansible"


def _read_text(relative_path: str) -> str:
    """Return the text content of a repository file."""
    return (ROOT / relative_path).read_text()


def _read_yaml(relative_path: str) -> Any:
    """Return the YAML-decoded content of a repository file."""
    return yaml.safe_load((ROOT / relative_path).read_text())


class TestBaikalContracts:
    """Guardrails for Baikal's declarative PostgreSQL wiring."""

    def test_baikal_uses_host_access_name_without_inline_port(self) -> None:
        """Baikal must pass only the host-access name to pgsql_host."""
        defaults = _read_yaml("ansible/apps/baikal/defaults/main.yml")

        assert isinstance(defaults, dict)
        assert defaults["baikal_db_host"] == "{{ postgres_host_access_name }}"

    def test_baikal_uses_default_container_network(self) -> None:
        """Baikal should not depend on a custom Podman bridge network."""
        template = _read_text("ansible/apps/baikal/templates/baikal.container.j2")

        assert "Network=" not in template

    def test_baikal_marks_installation_complete(self) -> None:
        """Declarative provisioning must disable the installer route afterwards."""
        tasks = _read_text("ansible/apps/baikal/tasks/main.yml")

        assert "Disable Baikal install tool after declarative provisioning" in tasks
        assert "INSTALL_DISABLED" in tasks


class TestCleanupContracts:
    """Guardrails for the cleanup playbook and per-app teardown tasks."""

    def test_cleanup_playbook_requires_cleanup_app(self) -> None:
        """cleanup.yml must assert that cleanup_app is defined before doing anything."""
        playbook = _read_text("ansible/cleanup.yml")

        assert "cleanup_app is defined" in playbook

    def test_cleanup_playbook_has_confirmation_prompt(self) -> None:
        """cleanup.yml must pause for confirmation before destructive steps."""
        playbook = _read_text("ansible/cleanup.yml")

        assert "ansible.builtin.pause" in playbook
        assert "PERMANENTLY DELETE" in playbook

    def test_postgres_cleanup_aborts_if_baikal_still_deployed(self) -> None:
        """Postgres cleanup must refuse to run if the baikal quadlet still exists."""
        tasks = _read_text("ansible/apps/postgres/tasks/cleanup.yml")

        assert "baikal.container" in tasks
        assert "ansible.builtin.fail" in tasks

    def test_baikal_cleanup_drops_database(self) -> None:
        """Baikal cleanup must drop the baikal database from the postgres container."""
        tasks = _read_text("ansible/apps/baikal/tasks/cleanup.yml")

        assert "dropdb" in tasks
        assert "postgres_service_name" in tasks


class TestAnsibleStructureContracts:
    """Guardrails for Ansible structural patterns that have caused runtime failures."""

    def test_no_app_meta_dependencies(self) -> None:
        """App meta files must declare empty dependencies — ordering belongs in site.yml tags.

        Non-empty meta dependencies cause roles to run multiple times under tag-based
        invocation, which can time out on repeated privilege escalation.
        """
        for meta_file in sorted((ANSIBLE_DIR / "apps").glob("*/meta/main.yml")):
            data = _read_yaml(f"ansible/apps/{meta_file.parent.parent.name}/meta/main.yml")
            assert isinstance(data, dict)
            assert "dependencies" not in data or data["dependencies"] == [], (
                f"{meta_file.parent.parent.name}/meta/main.yml has non-empty dependencies; "
                "declare ordering via site.yml tags instead"
            )

    def test_cleanup_does_not_use_include_vars(self) -> None:
        """cleanup.yml must not use include_vars to load role defaults.

        include_vars has higher precedence than host_vars, so loading a defaults file
        that contains null-sentinel required vars (e.g. postgres_data_path: ~) silently
        overrides the host_vars values, causing file-removal tasks to no-op.
        """
        playbook = _read_text("ansible/cleanup.yml")

        assert "include_vars:" not in playbook


class TestPostgresContracts:
    """Guardrails for PostgreSQL network and auth wiring."""

    def test_postgres_hba_template_allows_host_access_network(self) -> None:
        """The managed HBA file must allow rootless host-access traffic."""
        template = _read_text("ansible/apps/postgres/templates/postgres.hba.conf.j2")

        assert "{{ ansible_facts['default_ipv4']['address'] }}/32" in template
        assert "169.254.0.0/16" in template

    def test_postgres_container_uses_managed_hba_file_without_custom_network(self) -> None:
        """PostgreSQL must mount HBA explicitly and avoid a custom bridge network."""
        template = _read_text("ansible/apps/postgres/templates/postgres.container.j2")

        assert "Exec=postgres -c hba_file={{ postgres_hba_container_path }}" in template
        assert (
            "Volume={{ postgres_hba_host_path }}:{{ postgres_hba_container_path }}:ro" in template
        )
        assert "Network=" not in template

    def test_postgres_role_renders_managed_hba_template_and_flushes_changes(self) -> None:
        """The PostgreSQL role must apply config changes before dependent roles run."""
        tasks = _read_text("ansible/apps/postgres/tasks/main.yml")

        assert "Install PostgreSQL pg_hba.conf" in tasks
        assert "src: postgres.hba.conf.j2" in tasks
        assert "Remove legacy PostgreSQL Podman network quadlet" in tasks
        assert "Apply pending PostgreSQL handler changes" in tasks
        assert "ansible.builtin.meta: flush_handlers" in tasks
        assert "lineinfile" not in tasks
