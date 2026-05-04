"""Host inventory management commands."""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from linux_hi.models import ANSIBLE_DATA
from linux_hi.services.vault import remove_become_password, write_become_password
from linux_hi.utils.exec import resolve_executable, run_resolved

_console = Console()


def _pick(*values: str | None) -> str | None:
    """Return the first non-empty string in *values* or None."""
    for value in values:
        if value:
            return value
    return None


def _prompt_if_missing(value: str | None, label: str, default: str | None = None) -> str | None:
    """Prompt with *label* when *value* is missing, preserving an optional default."""
    if value:
        return value
    return questionary.text(label, default=default or "").ask()


def _resolve_port(value: int | None) -> int:
    """Resolve CLI/env/prompt port input into an integer or terminate on invalid input."""
    if value is not None:
        return value
    port_raw = os.environ.get("PORT") or questionary.text("SSH port:", default="22").ask()
    if not port_raw:
        sys.exit("Aborted.")
    try:
        return int(port_raw)
    except ValueError:
        sys.exit("  [FAIL]  PORT must be an integer.")


def _default_interface() -> str | None:
    """Return the network interface used by the default route, or None."""
    try:
        out = run_resolved(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        tokens = out.split()
        for i, tok in enumerate(tokens):
            if tok == "dev" and i + 1 < len(tokens):
                return tokens[i + 1]
    except Exception:
        return None
    return None


def _local_subnet() -> str | None:
    """Return the LAN subnet CIDR for the default route's interface, or None."""
    dev = _default_interface()
    if not dev:
        return None
    try:
        out = run_resolved(
            ["ip", "route", "show", "dev", dev, "scope", "link"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        for line in out.splitlines():
            cidr = line.split()[0]
            if "/" in cidr:
                return cidr
    except Exception:
        return None
    return None


def _arp_candidates(iface: str) -> list[str]:
    """Return IPs from the ARP cache on *iface* with a complete entry (flags=0x2)."""
    try:
        lines = Path("/proc/net/arp").read_text().splitlines()[1:]
        return [
            parts[0]
            for line in lines
            if (parts := line.split())
            and len(parts) >= 6
            and parts[5] == iface
            and parts[2] == "0x2"
        ]
    except Exception:
        return []


def _scan_ssh_hosts() -> list[str]:
    """Return IPs with port 22 open on the LAN.

    Tries nmap first (thorough, finds devices not yet in ARP cache). Falls back
    to probing ARP cache entries over TCP when nmap is not installed.
    """
    iface = _default_interface()
    subnet = _local_subnet()
    if not subnet:
        return []

    _console.print(f"  [INFO]  Scanning {subnet} for SSH hosts…", style="dim")

    try:
        nmap = resolve_executable("nmap")
    except FileNotFoundError:
        nmap = None

    if nmap:
        try:
            out = run_resolved(
                ["nmap", "-p", "22", "--open", "-oG", "-", subnet],
                capture_output=True,
                text=True,
                timeout=60,
            ).stdout
            hosts = []
            for line in out.splitlines():
                if not (line.startswith("Host:") and "22/open" in line):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    hosts.append(parts[1])
            return hosts
        except Exception:
            return []

    # nmap unavailable — probe known-reachable hosts from the ARP cache.
    candidates = _arp_candidates(iface) if iface else []
    return [ip for ip in candidates if _port_open(ip, 22)]


def _port_open(addr: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if *addr*:*port* accepts a TCP connection."""
    try:
        with socket.create_connection((addr, port), timeout=timeout):
            return True
    except OSError:
        return False


_PROJECT_KEY = Path("ansible/config/.ed25519")


def _ensure_project_key() -> Path:
    """Return the project SSH key path, generating or repairing the keypair as needed."""
    pub = Path(str(_PROJECT_KEY) + ".pub")
    _PROJECT_KEY.parent.mkdir(parents=True, exist_ok=True)

    if not _PROJECT_KEY.exists():
        _console.print(
            f"  [INFO]  Generating project SSH key at {_PROJECT_KEY}…", style="dim"
        )
        run_resolved(
            ["ssh-keygen", "-t", "ed25519", "-f", str(_PROJECT_KEY), "-N", ""],
            check=True, capture_output=True,
        )
    elif not pub.exists():
        _console.print(
            f"  [INFO]  Deriving missing public key from {_PROJECT_KEY}…", style="dim"
        )
        result = run_resolved(
            ["ssh-keygen", "-y", "-f", str(_PROJECT_KEY)],
            capture_output=True, text=True, check=True,
        )
        pub.write_text(result.stdout)

    return _PROJECT_KEY


def _copy_public_key(key: Path, user: str, addr: str, port: int) -> bool:
    """Copy *key*.pub to the remote host's authorized_keys.

    Tries password auth first (ssh-copy-id interactive). If the host only
    accepts publickey auth, prompts for an existing bootstrap key to use
    instead, then installs the project key via that key.
    """
    pub = Path(str(key) + ".pub")
    if not pub.exists():
        return False

    try:
        result = run_resolved(
            [
                "ssh-copy-id", "-i", str(pub),
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "PreferredAuthentications=keyboard-interactive,password",
                "-p", str(port), f"{user}@{addr}",
            ],
        )
        if result.returncode == 0:
            return True
    except Exception:
        return False

    # Password auth not available — device requires an existing trusted key.
    _console.print(
        "  [INFO]  Password auth unavailable. Provide the key you used when imaging this device.",
        style="dim",
    )
    bootstrap = questionary.text("Bootstrap key path (blank to cancel):").ask()
    if not bootstrap:
        return False

    pub_content = pub.read_text().strip()
    try:
        result = run_resolved(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "BatchMode=yes",
                "-i", bootstrap,
                "-p", str(port),
                f"{user}@{addr}",
                f"mkdir -p ~/.ssh && chmod 700 ~/.ssh"
                f" && grep -qxF {pub_content!r} ~/.ssh/authorized_keys 2>/dev/null"
                f" || echo {pub_content!r} >> ~/.ssh/authorized_keys"
                f" && chmod 600 ~/.ssh/authorized_keys",
            ],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _test_connection(addr: str, user: str, port: int, key: str | None) -> bool:
    """Return True if the host is reachable over SSH with the given credentials."""
    if key:
        try:
            result = run_resolved(
                [
                    "ssh",
                    "-o",
                    "ConnectTimeout=5",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-i",
                    key,
                    "-p",
                    str(port),
                    f"{user}@{addr}",
                    "true",
                ],
                capture_output=True,
                timeout=15,
            )
            return result.returncode == 0
        except Exception:
            return False
    return _port_open(addr, port, timeout=5.0)


def cmd_list(args: argparse.Namespace) -> None:
    """Print a table of configured inventory hosts and their connection details."""
    table = Table(show_header=True, header_style="bold")
    for col in ("name", "host", "user", "port", "key"):
        table.add_column(col)
    for alias in ANSIBLE_DATA.inventory_hosts():
        hv = ANSIBLE_DATA.host_vars(alias)
        key = Path(hv.ansible_ssh_private_key_file).name if hv.ansible_ssh_private_key_file else "—"
        table.add_row(
            alias, hv.ansible_host, hv.ansible_user or "—", str(hv.ansible_port or 22), key
        )
    _console.print(table)


def cmd_add(args: argparse.Namespace) -> None:
    """Interactively add a host to inventory, host_vars, and vault."""
    from typing import cast

    name = _prompt_if_missing(_pick(args.name, os.environ.get("NAME")), "Host alias:")

    addr_arg = _pick(args.address, os.environ.get("ADDRESS"), os.environ.get("ADDR"))
    if addr_arg:
        addr = addr_arg
    else:
        discovered = _scan_ssh_hosts()
        if discovered:
            choices = [*discovered, "Enter manually"]
            selection = questionary.select("Select a host:", choices=choices).ask()
            if not selection:
                sys.exit("Aborted.")
            addr = (
                questionary.text("Address (IP, mDNS, or hostname):").ask()
                if selection == "Enter manually"
                else selection
            )
        else:
            addr = questionary.text("Address (IP, mDNS, or hostname):").ask()

    user = _prompt_if_missing(_pick(args.user), "SSH user:", default="pi")
    port = _resolve_port(args.port)

    if not all([name, addr, user]):
        sys.exit("Aborted.")

    _console.print(f"  [INFO]  Checking {addr}:{port} is reachable…", style="dim")
    if not _port_open(cast(str, addr), port, timeout=5.0):
        sys.exit(f"  [FAIL]  {addr}:{port} is not reachable. Check address and port.")

    key = _ensure_project_key()
    _console.print(
        f"  [INFO]  Copying {key}.pub to {user}@{addr} — authenticate when prompted.",
        style="dim",
    )
    if not _copy_public_key(key, cast(str, user), cast(str, addr), port):
        sys.exit(f"  [FAIL]  Could not copy SSH key to {user}@{addr}:{port}.")

    _console.print("  [INFO]  Verifying SSH key auth…", style="dim")
    if not _test_connection(cast(str, addr), cast(str, user), port, str(key)):
        sys.exit(f"  [FAIL]  SSH key auth failed for {user}@{addr}:{port} after copy.")

    password = questionary.password(f"Become (sudo) password for '{name}':").ask()
    if not password:
        sys.exit("Aborted.")

    host_vars_data: dict[str, object] = {
        "ansible_host": addr,
        "ansible_user": user,
        "ansible_port": port,
        "ansible_ssh_private_key_file": str(key),
        "ansible_become_password": (
            "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
        ),
    }

    try:
        ANSIBLE_DATA.add_inventory_host(cast(str, name))
        ANSIBLE_DATA.write_host_vars_raw(cast(str, name), host_vars_data)
        write_become_password(cast(str, name), cast(str, password))
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Host '{name}' added to inventory, host_vars, and vault.")


def cmd_remove(args: argparse.Namespace) -> None:
    """Interactively remove a host from inventory, host_vars, and vault."""
    hosts = ANSIBLE_DATA.inventory_hosts()
    if not hosts:
        sys.exit("No hosts configured.")

    name = args.name or os.environ.get("NAME")
    if not name:
        name = questionary.select("Select host to remove:", choices=hosts).ask()
    if not name:
        sys.exit("Aborted.")
    if name not in hosts:
        sys.exit(f"  [FAIL]  Host '{name}' not found in inventory.")

    try:
        ANSIBLE_DATA.remove_inventory_host(name)
        ANSIBLE_DATA.remove_host_vars(name)
        remove_become_password(name)
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Host '{name}' removed from inventory, host_vars, and vault.")


def main(argv: list[str] | None = None) -> None:
    """Dispatch host management subcommands."""
    parser = argparse.ArgumentParser(description="Host inventory management")
    parser.set_defaults(func=cmd_list)
    sub = parser.add_subparsers()

    list_p = sub.add_parser("list", help="List configured hosts")
    list_p.set_defaults(func=cmd_list)

    add_p = sub.add_parser("add", help="Add a host to inventory")
    add_p.add_argument("--name")
    add_p.add_argument("--address")
    add_p.add_argument("--secret")
    add_p.add_argument("--user")
    add_p.add_argument("--port", type=int)
    add_p.set_defaults(func=cmd_add)

    rm_p = sub.add_parser("remove", help="Remove a host from inventory")
    rm_p.add_argument("--name")
    rm_p.set_defaults(func=cmd_remove)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
