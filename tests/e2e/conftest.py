"""E2E fixtures — require a live host reachable over SSH.

The HOST env var selects the target host (default: rpi), matching the Makefile convention.
Run with: make test-e2e   or   HOST=myserver make test-e2e
"""

from __future__ import annotations

import os

import pytest

from models import ANSIBLE_DATA
from scripts.utils.ansible_utils import make_connection
from scripts.utils.connection_types import RemoteConnection


@pytest.fixture(scope="session")
def live_conn() -> RemoteConnection:
    """Fabric Connection to the host selected by HOST (default: rpi)."""
    host = os.environ.get("HOST", "rpi")
    hvars = ANSIBLE_DATA.host_vars(host)
    return make_connection(hvars)
