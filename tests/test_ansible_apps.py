"""Contract tests for Ansible app wiring that has broken before."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE_DIR = ROOT / "ansible"


def _read_text(relative_path: str) -> str:
    """Return the text content of a repository file."""
    return (ROOT / relative_path).read_text()


def _read_yaml(relative_path: str) -> object:
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


class TestPostgresContracts:
    """Guardrails for PostgreSQL network and auth wiring."""

    def test_postgres_hba_template_allows_host_access_network(self) -> None:
        """The managed HBA file must allow rootless host-access traffic."""
        template = _read_text("ansible/apps/postgres/templates/postgres.hba.conf.j2")

        assert "{{ ansible_default_ipv4.address }}/32" in template
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
