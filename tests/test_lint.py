"""Linting tests — fail fast if the codebase has ruff violations."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from scripts.utils.exec_utils import run_resolved

ROOT = Path(__file__).resolve().parents[1]


class TestCpd:
    """Ensure the codebase passes copy-paste detection checks."""

    def test_cpd(self):
        """Fail if jscpd reports copy-paste duplication above the threshold."""
        result = run_resolved(
            [
                "npx",
                "jscpd",
                "--format",
                "python",
                "--min-tokens",
                "50",
                "--threshold",
                "3",
                "--ignore",
                "**/.venv/**,**/typings/**",
                ".",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestRuff:
    """Ensure the codebase passes ruff linting and formatting checks."""

    PATHS = ["scripts/", "models/", "tests/"]

    def test_ruff_check(self):
        """Fail if ruff reports any lint violations."""
        result = run_resolved(
            ["poetry", "run", "ruff", "check", *self.PATHS],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_ruff_format(self):
        """Fail if ruff reports any formatting violations."""
        result = run_resolved(
            ["poetry", "run", "ruff", "format", "--check", *self.PATHS],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestPyright:
    """Ensure the codebase passes the current Pyright gate."""

    def test_pyright(self):
        """Fail if Pyright reports any type-checking violations."""
        result = run_resolved(
            ["poetry", "run", "pyright"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestSemgrep:
    """Ensure the codebase passes the current Semgrep architecture gate."""

    def test_semgrep(self):
        """Fail if Semgrep reports any architecture or process violations."""
        result = run_resolved(
            ["poetry", "run", "semgrep", "scan", "--config", ".semgrep.yml", "--error"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestAnsibleLint:
    """Ensure the Ansible roles pass ansible-lint."""

    def test_ansible_config_does_not_require_local_vault_password(self):
        """Global Ansible config must not depend on a developer-only vault file."""
        config = configparser.ConfigParser()
        config.read(ROOT / "ansible" / "ansible.cfg")

        assert "vault_password_file" not in config["defaults"]

    def test_ansible_lint(self):
        """Fail if ansible-lint reports any role or playbook violations."""
        result = run_resolved(
            [
                "poetry",
                "run",
                "ansible-lint",
                "-x",
                "var-naming",
                "ansible/apps/postgres",
                "ansible/apps/baikal",
                "ansible/roles/service_adapter",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "ANSIBLE_CONFIG": "ansible/ansible.cfg"},
        )
        assert result.returncode == 0, result.stdout + result.stderr
