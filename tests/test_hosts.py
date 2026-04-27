"""Tests for the host management CLI."""

from __future__ import annotations

import pytest

from linux_hi.cli.hosts import cmd_list
from models import ANSIBLE_DATA


def test_hosts_list_covers_all_inventory_hosts(capsys: pytest.CaptureFixture[str]) -> None:
    """hosts-list must display every host in the configured inventory."""
    cmd_list()
    captured = capsys.readouterr()
    for alias in ANSIBLE_DATA.inventory_hosts():
        assert alias in captured.out, f"Expected '{alias}' in hosts-list output"


def test_hosts_list_shows_connection_details(capsys: pytest.CaptureFixture[str]) -> None:
    """hosts-list must show ansible_host for at least one host."""
    cmd_list()
    captured = capsys.readouterr()
    hosts_with_explicit_host = [
        alias
        for alias in ANSIBLE_DATA.inventory_hosts()
        if ANSIBLE_DATA.host_vars(alias).ansible_host != alias
    ]
    for alias in hosts_with_explicit_host:
        hv = ANSIBLE_DATA.host_vars(alias)
        assert hv.ansible_host in captured.out, (
            f"Expected ansible_host '{hv.ansible_host}' for '{alias}' in hosts-list output"
        )
