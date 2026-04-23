"""Tests for rclone_utils — offline rclone config parsing."""

from __future__ import annotations

from linux_hi.storage.rclone import list_remotes, parse_rclone_config


class TestListRemotes:
    """Tests for list_remotes — parse remote names from rclone INI config."""

    def test_single_remote(self) -> None:
        """A single INI section is returned as one remote name."""
        config = "[pcloud]\ntype = pcloud\nclient_id = abc123\n"
        assert list_remotes(config) == ["pcloud"]

    def test_multiple_remotes(self) -> None:
        """Multiple sections are returned in declaration order."""
        config = "[pcloud]\ntype = pcloud\n\n[gdrive]\ntype = drive\n"
        assert list_remotes(config) == ["pcloud", "gdrive"]

    def test_empty_config(self) -> None:
        """Empty string yields no remotes."""
        assert list_remotes("") == []

    def test_whitespace_only(self) -> None:
        """Whitespace-only string yields no remotes."""
        assert list_remotes("   \n  \n") == []

    def test_remote_with_multiple_keys(self) -> None:
        """Remote sections with many keys still resolve to one name each."""
        config = (
            "[myremote]\n"
            "type = s3\n"
            "provider = Other\n"
            "access_key_id = AKID\n"
            "secret_access_key = SECRET\n"
            "endpoint = https://example.com\n"
        )
        assert list_remotes(config) == ["myremote"]

    def test_mapping_input(self) -> None:
        """Passing a structured mapping returns the remote names in order."""
        mapping = {
            "pcloud": {"type": "pcloud", "client_id": "abc"},
            "gdrive": {"type": "drive"},
        }
        assert list_remotes(mapping) == ["pcloud", "gdrive"]

    def test_parse_rclone_config_from_string_and_mapping(self) -> None:
        """parse_rclone_config accepts both INI strings and mappings."""
        ini = "[pcloud]\ntype = pcloud\n"
        parsed_from_str = parse_rclone_config(ini)
        assert parsed_from_str == {"pcloud": {"type": "pcloud"}}

        mapping = {"pcloud": {"type": "pcloud"}}
        parsed_from_map = parse_rclone_config(mapping)
        assert parsed_from_map == mapping
