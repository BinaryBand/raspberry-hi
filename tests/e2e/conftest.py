"""E2E fixtures — require a live host reachable over SSH.

The HOST env var selects the target host (default: rpi), matching the Makefile convention.
Run with: make test-e2e   or   HOST=myserver make test-e2e
"""

from __future__ import annotations

import os

import pytest

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.ansible.connection import make_connection
from linux_hi.models import ANSIBLE_DATA


@pytest.fixture(scope="session")
def selected_host() -> str:
    """Inventory host alias selected for e2e tests."""
    return os.environ.get("HOST", "rpi")


@pytest.fixture(scope="session")
def live_conn(selected_host: str) -> RemoteConnection:
    """Fabric Connection to the host selected by HOST (default: rpi)."""
    hvars = ANSIBLE_DATA.host_vars(selected_host)
    return make_connection(hvars)
