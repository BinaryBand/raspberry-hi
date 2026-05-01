"""Tests for the host management CLI and inventory helpers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from linux_hi.cli import hosts
from linux_hi.models import ANSIBLE_DATA
from linux_hi.models.ansible.access import AnsibleDataStore


def test_hosts_list_covers_all_inventory_hosts(capsys: pytest.CaptureFixture[str]) -> None:
    """hosts-list must display every host in the configured inventory."""
    hosts.cmd_list(argparse.Namespace())
    captured = capsys.readouterr()
    for alias in ANSIBLE_DATA.inventory_hosts():
        assert alias in captured.out, f"Expected '{alias}' in hosts-list output"


_MINIMAL_INVENTORY = "all:\n  children:\n    devices:\n      hosts:\n        rpi:\n"


def _temp_store(tmp_path: Path, content: str = _MINIMAL_INVENTORY) -> AnsibleDataStore:
    inv = tmp_path / "inventory" / "hosts.yml"
    inv.parent.mkdir(parents=True, exist_ok=True)
    inv.write_text(content, encoding="utf-8")
    return AnsibleDataStore.from_inventory_file(inv)


def test_add_inventory_host_appears_in_hosts(tmp_path: Path) -> None:
    """add_inventory_host must persist the new alias so inventory_hosts reflects it."""
    store = _temp_store(tmp_path)
    store.add_inventory_host("newhost")
    assert "newhost" in store.inventory_hosts()


def test_add_inventory_host_rejects_duplicate(tmp_path: Path) -> None:
    """Adding an alias that already exists must raise ValueError."""
    store = _temp_store(tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        store.add_inventory_host("rpi")


def test_remove_inventory_host_no_longer_in_hosts(tmp_path: Path) -> None:
    """remove_inventory_host must drop the alias while leaving others intact."""
    content = "all:\n  children:\n    devices:\n      hosts:\n        rpi:\n        rpi2:\n"
    store = _temp_store(tmp_path, content)
    store.remove_inventory_host("rpi")
    assert "rpi" not in store.inventory_hosts()
    assert "rpi2" in store.inventory_hosts()


def test_remove_inventory_host_rejects_unknown(tmp_path: Path) -> None:
    """Removing a host not in inventory must raise KeyError."""
    store = _temp_store(tmp_path)
    with pytest.raises(KeyError):
        store.remove_inventory_host("ghost")


def test_remove_host_vars_deletes_file(tmp_path: Path) -> None:
    """remove_host_vars must delete the host_vars file when it exists."""
    store = _temp_store(tmp_path)
    hv_file = store.host_vars_dir / "rpi.yml"
    hv_file.parent.mkdir(parents=True, exist_ok=True)
    hv_file.write_text("ansible_host: rpi.local\n", encoding="utf-8")
    store.remove_host_vars("rpi")
    assert not hv_file.exists()


def test_remove_host_vars_is_silent_when_missing(tmp_path: Path) -> None:
    """remove_host_vars must not raise when host_vars file does not exist."""
    store = _temp_store(tmp_path)
    store.remove_host_vars("rpi")  # no file created — must not raise


def test_hosts_list_shows_connection_details(capsys: pytest.CaptureFixture[str]) -> None:
    """hosts-list must show ansible_host for at least one host."""
    hosts.cmd_list(argparse.Namespace())
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


def test_pick_returns_first_non_empty_value() -> None:
    """_pick should return the first truthy value among candidates."""
    assert hosts._pick(None, "", "alpha", "beta") == "alpha"


def test_prompt_if_missing_uses_existing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """_prompt_if_missing should bypass questionary when value is already present."""
    called: list[str] = []

    def _ask() -> str:
        called.append("ask")
        return "unused"

    monkeypatch.setattr(hosts.questionary, "text", lambda *_a, **_k: type("Q", (), {"ask": _ask})())
    assert hosts._prompt_if_missing("existing", "Label") == "existing"
    assert called == []


def test_resolve_port_from_argument() -> None:
    """_resolve_port should return the explicit argument without prompting."""
    assert hosts._resolve_port(2222) == 2222


def test_resolve_port_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """_resolve_port should use PORT environment variable when argument is absent."""
    monkeypatch.setenv("PORT", "2200")
    assert hosts._resolve_port(None) == 2200


def test_resolve_port_rejects_non_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    """_resolve_port should exit with an error when non-integer input is provided."""
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(
        hosts.questionary,
        "text",
        lambda *_a, **_k: type("Q", (), {"ask": lambda self: "not-an-int"})(),
    )
    with pytest.raises(SystemExit):
        hosts._resolve_port(None)


def test_cmd_add_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_add should write inventory, host_vars, and vault entries on success."""
    calls: list[tuple[str, object]] = []

    class _Store:
        def add_inventory_host(self, name: str) -> None:
            calls.append(("add_inventory_host", name))

        def write_host_vars_raw(self, name: str, data: dict[str, object]) -> None:
            calls.append(("write_host_vars_raw", (name, data)))

    answers = iter(["rpi", "192.168.1.10", "pi", "/home/me/.ssh/id_ed25519", "s3cr3t"])

    monkeypatch.setattr(hosts, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(
        hosts.questionary,
        "text",
        lambda *_a, **_k: type("Q", (), {"ask": lambda self: next(answers)})(),
    )
    monkeypatch.setattr(
        hosts.questionary,
        "password",
        lambda *_a, **_k: type("Q", (), {"ask": lambda self: next(answers)})(),
    )
    monkeypatch.setattr(hosts, "write_become_password", lambda name, pwd: calls.append(("vault", (name, pwd))))

    args = argparse.Namespace(name=None, address=None, secret=None, user=None, port=22)
    hosts.cmd_add(args)

    assert any(c[0] == "add_inventory_host" for c in calls)
    assert any(c[0] == "write_host_vars_raw" for c in calls)
    assert any(c[0] == "vault" for c in calls)


def test_cmd_remove_unknown_host_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_remove should exit when requested host is not in inventory."""

    class _Store:
        def inventory_hosts(self) -> list[str]:
            return ["rpi"]

    monkeypatch.setattr(hosts, "ANSIBLE_DATA", _Store())

    with pytest.raises(SystemExit):
        hosts.cmd_remove(argparse.Namespace(name="ghost"))


def test_cmd_remove_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_remove should remove inventory, host vars, and become password for host."""
    calls: list[tuple[str, str]] = []

    class _Store:
        def inventory_hosts(self) -> list[str]:
            return ["rpi", "rpi2"]

        def remove_inventory_host(self, name: str) -> None:
            calls.append(("inventory", name))

        def remove_host_vars(self, name: str) -> None:
            calls.append(("host_vars", name))

    monkeypatch.setattr(hosts, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(hosts, "remove_become_password", lambda name: calls.append(("vault", name)))

    hosts.cmd_remove(argparse.Namespace(name="rpi"))

    assert calls == [("inventory", "rpi"), ("host_vars", "rpi"), ("vault", "rpi")]


def test_main_dispatches_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """main should dispatch to cmd_list when no subcommand is provided."""
    called: list[str] = []
    monkeypatch.setattr(hosts, "cmd_list", lambda _args: called.append("list"))
    hosts.main([])
    assert called == ["list"]
