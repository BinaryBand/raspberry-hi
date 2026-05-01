"""Unit tests for rclone CLI flow."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.cli import rclone


def test_main_exits_when_rclone_binary_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Main should exit with a clear message when rclone is unavailable."""
    conf_path = tmp_path / "rclone.conf"
    monkeypatch.setattr(rclone, "RCLONE_CONF", conf_path)

    def _missing(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(rclone, "run_resolved", _missing)

    with pytest.raises(SystemExit) as exc:
        rclone.main()

    assert "rclone is not installed" in str(exc.value)


def test_main_exits_when_config_is_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Main should fail when config file remains empty after rclone config runs."""
    conf_path = tmp_path / "rclone.conf"
    monkeypatch.setattr(rclone, "RCLONE_CONF", conf_path)
    monkeypatch.setattr(rclone, "run_resolved", lambda *_a, **_k: None)

    with pytest.raises(SystemExit) as exc:
        rclone.main()

    assert "No remotes configured" in str(exc.value)


def test_main_exits_when_no_remote_names_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Main should fail when parsed config contains no remotes."""
    conf_path = tmp_path / "rclone.conf"
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text("[dummy]\ntype = s3\n", encoding="utf-8")

    monkeypatch.setattr(rclone, "RCLONE_CONF", conf_path)
    monkeypatch.setattr(rclone, "run_resolved", lambda *_a, **_k: None)
    monkeypatch.setattr(rclone, "parse_rclone_ini", lambda _text: {})
    monkeypatch.setattr(rclone, "list_remotes", lambda _cfg: [])

    with pytest.raises(SystemExit) as exc:
        rclone.main()

    assert "No remotes found" in str(exc.value)


def test_main_aborts_when_overwrite_not_confirmed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Main should abort if vault already has remotes and user declines overwrite."""
    conf_path = tmp_path / "rclone.conf"
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text("[remote]\ntype = s3\n", encoding="utf-8")

    monkeypatch.setattr(rclone, "RCLONE_CONF", conf_path)
    monkeypatch.setattr(rclone, "run_resolved", lambda *_a, **_k: None)
    monkeypatch.setattr(rclone, "parse_rclone_ini", lambda _text: {"remote": {"type": "s3"}})
    monkeypatch.setattr(rclone, "list_remotes", lambda cfg: list(cfg.keys()))
    monkeypatch.setattr(
        rclone,
        "decrypt_vault_raw",
        lambda: {"rclone_config": {"old": {"type": "s3"}}},
    )
    monkeypatch.setattr(
        rclone.questionary,
        "confirm",
        lambda _msg: type("Q", (), {"ask": lambda self: False})(),
    )

    with pytest.raises(SystemExit) as exc:
        rclone.main()

    assert str(exc.value) == "Aborted."


def test_main_encrypts_and_replaces_vault_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Main should encrypt updated rclone config and atomically replace vault file."""
    conf_path = tmp_path / "config" / "rclone.conf"
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text("[remote]\ntype = s3\n", encoding="utf-8")

    vault_file = tmp_path / "vault.yml"
    vault_file.write_text("encrypted", encoding="utf-8")

    encrypted: list[tuple[dict[str, object], Path | None]] = []
    replaced: list[tuple[Path, Path]] = []

    monkeypatch.setattr(rclone, "RCLONE_CONF", conf_path)
    monkeypatch.setattr(rclone, "VAULT_FILE", vault_file)
    monkeypatch.setattr(rclone, "run_resolved", lambda *_a, **_k: None)
    monkeypatch.setattr(rclone, "parse_rclone_ini", lambda _text: {"remote": {"type": "s3"}})
    monkeypatch.setattr(rclone, "list_remotes", lambda cfg: list(cfg.keys()))
    monkeypatch.setattr(rclone, "decrypt_vault_raw", lambda: {})
    monkeypatch.setattr(
        rclone,
        "encrypt_vault",
        lambda data, output=None: encrypted.append((dict(data), output)),
    )
    monkeypatch.setattr(
        rclone.os,
        "replace",
        lambda src, dst: replaced.append((Path(src), Path(dst))),
    )

    rclone.main()

    assert encrypted
    payload, output_path = encrypted[-1]
    assert payload["rclone_config"] == {"remote": {"type": "s3"}}
    assert output_path == vault_file.with_suffix(".tmp")
    assert replaced == [(vault_file.with_suffix(".tmp"), vault_file)]
