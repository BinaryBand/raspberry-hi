from __future__ import annotations

import configparser
from pathlib import Path

from models import ANSIBLE_DATA

INVENTORY_FILE = ANSIBLE_DATA.inventory_dir / "hosts.ini"


def discover_hosts(inventory_file: Path = INVENTORY_FILE) -> list[str]:
    """Return all hostnames from the Ansible inventory without requiring Ansible."""
    parser = configparser.ConfigParser(allow_no_value=True)
    parser.read(inventory_file)
    seen: set[str] = set()
    hosts: list[str] = []
    for section in parser.sections():
        for host in parser.options(section):
            if host not in seen:
                seen.add(host)
                hosts.append(host)
    return hosts
