#!/usr/bin/env python3
"""Prompt for any MinIO vars that are required but not yet set in host_vars.

Reads which vars are required directly from the role's defaults/main.yml
(null sentinel = required). Neither this script nor Ansible maintains a
separate list — the defaults file is the single source of truth.

Usage:
  HOST=rpi make minio   (called automatically via _minio_preflight target)
"""

from __future__ import annotations

import os
import sys

import questionary

from utils.ansible_utils import (
    ANSIBLE_DIR,
    read_host_vars_raw,
    role_required_vars,
    write_host_vars_raw,
)

MINIO_ROLE = ANSIBLE_DIR / "apps" / "minio"


def main() -> None:
    hostname = os.environ.get("HOST", "rpi")
    required = role_required_vars(MINIO_ROLE)
    if not required:
        return

    hvars = read_host_vars_raw(hostname)
    missing = [v for v in required if not hvars.get(v)]
    if not missing:
        return

    print(f"  [WARN]  Missing required vars for '{hostname}' — please set them now.")
    updates: dict = {}
    for var in missing:
        value = questionary.text(f"  {var}:").ask()
        if not value:
            sys.exit(f"  [FAIL]  {var} is required. Aborting.")
        updates[var] = value

    write_host_vars_raw(hostname, updates)
    print(f"  [OK  ]  Wrote {len(updates)} var(s) to host_vars/{hostname}.yml")


if __name__ == "__main__":
    main()
