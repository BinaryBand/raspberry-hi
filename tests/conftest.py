"""Pytest fixtures — thin wrappers over tests/support/.

Keep logic out of here. If a fixture needs supporting code, put it in
tests/support/ and import it here.
"""

import pytest

from tests.support.connections import FakeConnection
from tests.support.data import FINDMNT_OUTPUT, LSBLK_OUTPUT


@pytest.fixture
def findmnt_conn() -> FakeConnection:
    """Connection that returns a realistic findmnt payload."""
    return FakeConnection({"findmnt": FINDMNT_OUTPUT})


@pytest.fixture
def lsblk_conn() -> FakeConnection:
    """Connection that returns a realistic lsblk payload."""
    return FakeConnection({"lsblk": LSBLK_OUTPUT})
