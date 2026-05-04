"""E2E fixtures — require a live host reachable over SSH.

HOST env var selects the target host (default: first SSH-capable inventory alias).
Run with: make test-e2e   or   HOST=myserver make test-e2e
"""

from __future__ import annotations

import os

import pytest

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.models import ANSIBLE_DATA
from linux_hi.models.ansible.connection import make_connection


@pytest.fixture(scope="session")
def selected_host() -> str:
    """Inventory host alias selected for e2e tests."""
    explicit = os.environ.get("HOST")
    if explicit:
        return explicit

    hosts = ANSIBLE_DATA.inventory_hosts()
    if not hosts:
        pytest.skip("No inventory hosts configured; set HOST to run e2e tests")

    for alias in hosts:
        raw = ANSIBLE_DATA.read_host_vars_raw(alias)
        conn_type = str(raw.get("ansible_connection", "")).lower()
        ansible_host = str(raw.get("ansible_host", alias))
        if conn_type != "local" and ansible_host not in {"localhost", "127.0.0.1", "::1"}:
            return alias

    return hosts[0]


@pytest.fixture(scope="session")
def live_conn(selected_host: str) -> RemoteConnection:
    """Fabric Connection to the host selected by HOST (or first inventory alias)."""
    hvars = ANSIBLE_DATA.host_vars(selected_host)
    return make_connection(hvars)
