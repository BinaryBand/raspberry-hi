"""Tests for rclone_utils — offline rclone config parsing."""

from __future__ import annotations

from scripts.utils.rclone_utils import list_remotes


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
