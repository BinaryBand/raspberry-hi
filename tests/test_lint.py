"""Linting tests — fail fast if the codebase has ruff violations."""

from __future__ import annotations

from scripts.utils.exec_utils import run_resolved


class TestCpd:
    """Ensure the codebase passes copy-paste detection checks."""

    def test_cpd(self):
        """Fail if jscpd reports copy-paste duplication above the threshold."""
        result = run_resolved(
            ["npx", "jscpd", "."],
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
