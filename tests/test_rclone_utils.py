"""Tests for rclone_utils — offline rclone config parsing."""

from __future__ import annotations

from linux_hi.storage.rclone import list_remotes, parse_rclone_ini


class TestListRemotes:
    """Tests for list_remotes — parse remote names from rclone INI config."""

    def test_single_remote(self) -> None:
        """A single INI section is returned as one remote name."""
        config = "[pcloud]\ntype = pcloud\nclient_id = abc123\n"
        parsed = parse_rclone_ini(config)
        assert list_remotes(parsed) == ["pcloud"]

    def test_multiple_remotes(self) -> None:
        """Multiple sections are returned in declaration order."""
        config = "[pcloud]\ntype = pcloud\n\n[gdrive]\ntype = drive\n"
        parsed = parse_rclone_ini(config)
        assert list_remotes(parsed) == ["pcloud", "gdrive"]

    def test_empty_config(self) -> None:
        """Empty string yields no remotes."""
        parsed = parse_rclone_ini("")
        assert list_remotes(parsed) == []

    def test_whitespace_only(self) -> None:
        """Whitespace-only string yields no remotes."""
        parsed = parse_rclone_ini("   \n  \n")
        assert list_remotes(parsed) == []

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
        parsed = parse_rclone_ini(config)
        assert list_remotes(parsed) == ["myremote"]

    def test_mapping_input(self) -> None:
        """Passing a structured mapping returns the remote names in order."""
        mapping = {
            "pcloud": {"type": "pcloud", "client_id": "abc"},
            "gdrive": {"type": "drive"},
        }
        assert list_remotes(mapping) == ["pcloud", "gdrive"]

    def test_parse_rclone_ini_from_string(self) -> None:
        """parse_rclone_ini accepts INI strings and returns the mapping."""
        ini = "[pcloud]\ntype = pcloud\n"
        parsed_from_str = parse_rclone_ini(ini)
        assert parsed_from_str == {"pcloud": {"type": "pcloud"}}
