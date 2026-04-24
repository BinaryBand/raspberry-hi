"""Linting tests that enforce repository quality and architecture gates."""

from __future__ import annotations

import configparser
import re
from pathlib import Path

import yaml

from linux_hi.process.exec import run_resolved
from models import VaultSecrets
from models.ansible.registry import AppRegistry

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


class TestTy:
    """Ensure the codebase passes the current ty gate."""

    def test_ty(self):
        """Fail if ty reports any type-checking violations."""
        result = run_resolved(
            ["poetry", "run", "ty", "check"],
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


# Vault keys whose names end in a recognised secret suffix are already caught
# by the generic host-vars-no-inline-secret-keys pattern-regex.
_GENERIC_SECRET_SUFFIX = re.compile(
    r".*(?:password|secret|token|api_key|private_key)$",
    re.IGNORECASE,
)


class TestVaultSchemaIntegrity:
    """Semgrep vault rules must stay in sync with VaultSecrets and the app registry."""

    def _semgrep_rules(self) -> dict[str, object]:
        semgrep = yaml.safe_load((ROOT / ".semgrep.yml").read_text(encoding="utf-8"))
        return {r["id"]: r for r in semgrep["rules"]}

    def test_become_password_rule_references_vault_schema_field(self) -> None:
        """Semgrep become-password rule must reference the exact VaultSecrets field name."""
        field = "become_passwords"
        assert field in VaultSecrets.model_fields, (
            f"{field!r} removed from VaultSecrets — update "
            "host-vars-become-password-must-use-vault-template"
        )
        rules = self._semgrep_rules()
        rule_text = yaml.safe_dump(rules["host-vars-become-password-must-use-vault-template"])
        assert field in rule_text, (
            f"Semgrep rule host-vars-become-password-must-use-vault-template "
            f"no longer references vault field {field!r}"
        )

    def test_registry_vault_keys_without_generic_suffix_are_in_semgrep(self) -> None:
        """Registry keys not covered by generic suffix patterns must be explicit in Semgrep."""
        registry = AppRegistry.model_validate(
            yaml.safe_load((ROOT / "ansible" / "registry.yml").read_text(encoding="utf-8"))
        )
        rules = self._semgrep_rules()
        rule_text = yaml.safe_dump(rules["host-vars-no-inline-secret-keys"])

        needs_explicit = {
            spec.key
            for entry in registry.apps.values()
            for spec in entry.vault_secrets
            if not _GENERIC_SECRET_SUFFIX.match(spec.key)
        }
        missing = [k for k in sorted(needs_explicit) if k not in rule_text]
        assert not missing, (
            f"Registry vault keys with non-generic names are missing from "
            f"host-vars-no-inline-secret-keys in .semgrep.yml: {missing}. "
            f"Add them explicitly or rename to end with a covered suffix "
            f"(password|secret|token|api_key|private_key)."
        )
