"""Linting tests — fail fast if the codebase has ruff violations."""

from __future__ import annotations

import ast
import configparser
import os
from pathlib import Path

from linux_hi.process.exec import run_resolved

ROOT = Path(__file__).resolve().parents[1]


class TestShimGuard:
    """Ensure compatibility shims in scripts/utils/ stay thin.

    Re-export shims must contain only imports and ``__all__`` declarations.
    Any function or class definition in a shim module signals that logic
    has drifted into the compatibility layer — failing the build forces it
    back into linux_hi where it belongs.

    The authoritative list of shim modules lives in scripts/utils/__init__.py
    (``SHIM_MODULES``). Add new re-export files there; add intentional
    implementations to ``INTENTIONAL_MODULES`` with a brief justification.
    """

    UTILS_DIR = ROOT / "scripts" / "utils"

    def _shim_modules(self) -> frozenset[str]:
        from scripts.utils import SHIM_MODULES  # noqa: PLC0415

        return SHIM_MODULES

    def test_shim_modules_are_classified(self):
        """Every .py file in scripts/utils/ must appear in SHIM_MODULES or INTENTIONAL_MODULES."""
        from scripts.utils import INTENTIONAL_MODULES, SHIM_MODULES  # noqa: PLC0415

        all_classified = SHIM_MODULES | INTENTIONAL_MODULES
        py_files = {p.stem for p in self.UTILS_DIR.glob("*.py") if p.stem != "__init__"}
        unclassified = py_files - all_classified
        assert not unclassified, (
            f"Unclassified module(s) in scripts/utils/: {sorted(unclassified)}\n"
            "Add each to SHIM_MODULES or INTENTIONAL_MODULES in scripts/utils/__init__.py."
        )

    def test_shim_modules_have_no_logic(self):
        """Re-export shims must not define any functions or classes."""
        violations: list[str] = []
        for name in self._shim_modules():
            path = self.UTILS_DIR / f"{name}.py"
            if not path.exists():
                violations.append(f"{name}.py: file missing")
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    violations.append(
                        f"{name}.py: defines {type(node).__name__} "
                        f"'{node.name}' at line {node.lineno}"
                    )
        assert not violations, (
            "Shim module(s) contain logic — move it to linux_hi.* instead:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


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
                "ansible/apps/minio",
                "ansible/apps/postgres",
                "ansible/apps/baikal",
                "ansible/apps/restic",
                "ansible/roles/service_adapter",
                "ansible/roles/rclone",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "ANSIBLE_CONFIG": "ansible/ansible.cfg"},
        )
        assert result.returncode == 0, result.stdout + result.stderr
