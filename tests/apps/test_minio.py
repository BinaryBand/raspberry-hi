"""App-specific contract tests for MinIO.

MinIO has unique readiness-polling behaviour (health endpoint + mc alias) that
is not shared by other apps.  These checks live here rather than in
test_ansible_apps.py so that the generic suite stays app-agnostic.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_minio_bucket_setup_fails_when_health_poll_never_succeeds() -> None:
    """MinIO bucket setup must stop before mc commands if readiness polling never succeeds."""
    content = _read_text("ansible/roles/minio/tasks/setup_mc_bucket.yml")
    assert "Wait until MinIO health endpoint responds HTTP 200" in content
    assert "Fail if MinIO health endpoint never became ready" in content
