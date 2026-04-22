"""Linting tests that enforce repository quality and architecture gates."""

from __future__ import annotations

import configparser
from pathlib import Path

from linux_hi.process.exec import run_resolved

ROOT = Path(__file__).resolve().parents[1]


class TestCpd:
    """Ensure the codebase passes copy-paste detection checks."""

    def test_cpd(self):
        """Fail if jscpd reports any copy-paste duplication."""
        result = run_resolved(
            [
                "npx",
                "jscpd",
                "--format",
                "python",
                "--min-tokens",
                "50",
                "--threshold",
                "0",
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

    PATHS = ["linux_hi/", "scripts/", "models/", "tests/"]

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


class TestVulture:
    """Ensure the codebase passes the current Vulture dead-code gate."""

    PATHS = ["linux_hi/", "scripts/", "models/", "tests/"]

    def test_vulture(self):
        """Fail if Vulture reports unused code at or above 80% confidence."""
        result = run_resolved(
            ["poetry", "run", "vulture", "--min-confidence", "80", *self.PATHS],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestMakefileLint:
    """Ensure the repository Makefile passes style checks."""

    def test_makefile_style(self):
        """Fail if mbake reports Makefile formatting or style violations."""
        result = run_resolved(
            ["poetry", "run", "mbake", "format", "--check", "Makefile"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestAnsibleLint:
    """Ensure ansible configuration invariants remain valid."""

    def test_ansible_config_does_not_require_local_vault_password(self):
        """Global Ansible config must not depend on a developer-only vault file."""
        config = configparser.ConfigParser()
        config.read(ROOT / "ansible" / "ansible.cfg")

        assert "vault_password_file" not in config["defaults"]
