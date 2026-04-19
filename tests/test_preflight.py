"""Tests for preflight.py adapters — AnsibleRoleAdapter and VaultSecretsAdapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scripts.preflight import AnsibleRoleAdapter, VaultSecretsAdapter


def _write_preflight(role_path: Path, data: dict[str, Any]) -> None:
    (role_path / "preflight.yml").write_text(yaml.dump(data))


def _write_defaults(role_path: Path, defaults: dict[str, Any]) -> None:
    d = role_path / "defaults"
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.yml").write_text(yaml.dump(defaults))


class TestAnsibleRoleAdapter:
    """Tests for AnsibleRoleAdapter — reads required vars and hints from the role."""

    def test_hints_from_preflight_yml(self, tmp_path: Path) -> None:
        """Hints defined in preflight.yml are returned for matching var names."""
        _write_defaults(tmp_path, {"data_path": None, "port": 9000})
        _write_preflight(tmp_path, {"var_hints": {"data_path": "where to store data"}})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.required() == ["data_path"]
        assert adapter.hint("data_path") == "where to store data"
        assert adapter.hint("port") == ""

    def test_missing_preflight_yml_returns_empty_hints(self, tmp_path: Path) -> None:
        """Falls back to empty hint when no preflight.yml exists."""
        _write_defaults(tmp_path, {"data_path": None})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.required() == ["data_path"]
        assert adapter.hint("data_path") == ""

    def test_hidden_always_false(self, tmp_path: Path) -> None:
        """Host vars are never treated as hidden (no password masking)."""
        _write_defaults(tmp_path, {"secret": None})
        _write_preflight(tmp_path, {"var_hints": {"secret": "a secret"}})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.hidden("secret") is False

    def test_no_required_vars_when_defaults_all_set(self, tmp_path: Path) -> None:
        """Vars with concrete defaults are not flagged as required."""
        _write_defaults(tmp_path, {"port": 9000, "image": "minio:latest"})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.required() == []

    def test_missing_defaults_returns_empty(self, tmp_path: Path) -> None:
        """Returns no required vars when defaults/main.yml is absent."""
        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.required() == []

    def test_dict_hint_with_default(self, tmp_path: Path) -> None:
        """Dict-style hint entry exposes both hint text and prompt default."""
        _write_defaults(tmp_path, {"data_path": None})
        _write_preflight(
            tmp_path,
            {
                "var_hints": {
                    "data_path": {
                        "hint": "where to store data",
                        "default": "/home/linux-hi/app",
                    }
                }
            },
        )

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.hint("data_path") == "where to store data"
        assert adapter.default("data_path") == "/home/linux-hi/app"

    def test_dict_hint_without_default(self, tmp_path: Path) -> None:
        """Dict-style hint with no default field returns None for default."""
        _write_defaults(tmp_path, {"data_path": None})
        _write_preflight(tmp_path, {"var_hints": {"data_path": {"hint": "where to store data"}}})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.hint("data_path") == "where to store data"
        assert adapter.default("data_path") is None

    def test_string_hint_returns_none_default(self, tmp_path: Path) -> None:
        """Plain string hint (legacy format) returns None for default."""
        _write_defaults(tmp_path, {"data_path": None})
        _write_preflight(tmp_path, {"var_hints": {"data_path": "where to store data"}})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.hint("data_path") == "where to store data"
        assert adapter.default("data_path") is None

    def test_default_for_unknown_var_returns_none(self, tmp_path: Path) -> None:
        """default() returns None for vars not listed in var_hints."""
        _write_defaults(tmp_path, {"data_path": None})
        _write_preflight(tmp_path, {"var_hints": {}})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.default("data_path") is None

    def test_rclone_remote_type(self, tmp_path: Path) -> None:
        """var_type returns 'rclone_remote' when declared in preflight.yml."""
        _write_defaults(tmp_path, {"media_remote": None})
        _write_preflight(
            tmp_path,
            {
                "var_hints": {
                    "media_remote": {"hint": "rclone remote for media", "type": "rclone_remote"}
                }
            },
        )

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.var_type("media_remote") == "rclone_remote"
        assert adapter.hint("media_remote") == "rclone remote for media"

    def test_var_type_absent_returns_none(self, tmp_path: Path) -> None:
        """var_type returns None when no type field is declared."""
        _write_defaults(tmp_path, {"data_path": None})
        _write_preflight(tmp_path, {"var_hints": {"data_path": {"hint": "where to store data"}}})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.var_type("data_path") is None

    def test_var_type_for_unknown_var_returns_none(self, tmp_path: Path) -> None:
        """var_type returns None for vars absent from var_hints."""
        _write_defaults(tmp_path, {"data_path": None})
        _write_preflight(tmp_path, {"var_hints": {}})

        adapter = AnsibleRoleAdapter(tmp_path)

        assert adapter.var_type("data_path") is None


class TestVaultSecretsAdapter:
    """Tests for VaultSecretsAdapter — reads vault secret specs from the role."""

    def test_vault_secrets_from_preflight_yml(self, tmp_path: Path) -> None:
        """Reads key, label, and hidden from vault_secrets list."""
        _write_preflight(
            tmp_path,
            {
                "vault_secrets": [
                    {"key": "root_user", "label": "Root username", "hidden": False},
                    {"key": "root_password", "label": "Root password", "hidden": True},
                ]
            },
        )

        adapter = VaultSecretsAdapter(tmp_path)

        assert adapter.required() == ["root_user", "root_password"]
        assert adapter.hint("root_user") == "Root username"
        assert adapter.hint("root_password") == "Root password"

    def test_missing_preflight_yml_returns_no_secrets(self, tmp_path: Path) -> None:
        """Returns empty required list when no preflight.yml exists."""
        adapter = VaultSecretsAdapter(tmp_path)

        assert adapter.required() == []

    def test_hidden_secret(self, tmp_path: Path) -> None:
        """hidden=True causes password masking; hidden=False does not."""
        _write_preflight(
            tmp_path,
            {
                "vault_secrets": [
                    {"key": "username", "label": "Username", "hidden": False},
                    {"key": "password", "label": "Password", "hidden": True},
                ]
            },
        )

        adapter = VaultSecretsAdapter(tmp_path)

        assert adapter.hidden("username") is False
        assert adapter.hidden("password") is True

    def test_hint_for_unknown_key_returns_empty(self, tmp_path: Path) -> None:
        """hint() and hidden() return safe defaults for unrecognised keys."""
        _write_preflight(
            tmp_path,
            {"vault_secrets": [{"key": "token", "label": "API token", "hidden": True}]},
        )

        adapter = VaultSecretsAdapter(tmp_path)

        assert adapter.hint("nonexistent") == ""
        assert adapter.hidden("nonexistent") is False

    def test_var_type_always_none(self, tmp_path: Path) -> None:
        """VaultSecretsAdapter.var_type always returns None — vault secrets have no type."""
        _write_preflight(
            tmp_path,
            {"vault_secrets": [{"key": "token", "label": "API token", "hidden": True}]},
        )

        adapter = VaultSecretsAdapter(tmp_path)

        assert adapter.var_type("token") is None
