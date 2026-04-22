from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from codex_manager.account_status import patch_metadata


def test_patch_metadata_local_update_fail(mocker, tmp_path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    email = "test@example.com"
    archive_name = f"2026-04-19-100200-{email}-codex.metadata.json"
    metadata_path = backup_dir / archive_name
    metadata_path.write_text("invalid json", encoding="utf-8")

    class Args:
        pass

    args = Args()
    args.backup_dir = str(backup_dir)
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    mocker.patch("codex_manager.account_status.update_registry_entry")

    patch_metadata(email, reset_at=now, args=args)

    captured = capsys.readouterr()
    assert "Failed to patch local metadata" in captured.out

def test_patch_metadata_fallback_datetime_parsing(mocker, tmp_path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    email = "test@example.com"
    archive_name = f"2026-04-19-100200-{email}-codex.metadata.json"
    metadata_path = backup_dir / archive_name
    metadata_path.write_text(json.dumps({"email": email, "reset_at": "invalid_date", "session_start_at": "invalid_date"}), encoding="utf-8")

    class Args:
        pass

    args = Args()
    args.backup_dir = str(backup_dir)

    mock_update = mocker.patch("codex_manager.account_status.update_registry_entry")

    patch_metadata(email, args=args)

    # Make sure we didn't crash parsing invalid dates, they just fall through
    mock_update.assert_called_once()

from codex_manager.account_status import sync_current_account_status
from codex_manager.status import TokenExpiredError


def test_sync_current_account_status_no_email(tmp_path, capsys):
    class Args:
        dest_dir = str(tmp_path)
    args = Args()

    sync_current_account_status(args)

    captured = capsys.readouterr()
    assert "Could not identify current account from auth.json" in captured.out


def test_sync_current_account_status_token_expired(mocker, tmp_path, capsys):
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    auth_path = dest_dir / "auth.json"
    auth_path.write_text('{"email": "test@example.com"}', encoding="utf-8")

    class Args:
        pass

    args = Args()
    args.dest_dir = str(dest_dir)
    args.without_status_check = False
    args.command = "test"
    args.reference_year = 2026
    args.dry_run = False

    mocker.patch("codex_manager.account_status.read_status_text_from_args", side_effect=TokenExpiredError("expired", "raw_output"))
    mock_patch = mocker.patch("codex_manager.account_status.patch_metadata")

    with pytest.raises(SystemExit):
        sync_current_account_status(args)

    captured = capsys.readouterr()
    assert "Error:" in captured.out
    mock_patch.assert_called()

def test_sync_current_account_status_generic_error(mocker, tmp_path, capsys):
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    auth_path = dest_dir / "auth.json"
    auth_path.write_text('{"email": "test@example.com"}', encoding="utf-8")

    class Args:
        pass

    args = Args()
    args.dest_dir = str(dest_dir)
    args.without_status_check = False
    args.command = "test"
    args.reference_year = 2026

    mocker.patch("codex_manager.account_status.read_status_text_from_args", side_effect=Exception("some error"))

    with pytest.raises(SystemExit):
        sync_current_account_status(args)

    captured = capsys.readouterr()
    assert "Status capture failed twice" in captured.out


def test_sync_current_account_status_success(mocker, tmp_path, capsys):
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    auth_path = dest_dir / "auth.json"
    auth_path.write_text('{"email": "test@example.com"}', encoding="utf-8")

    class Args:
        pass

    args = Args()
    args.dest_dir = str(dest_dir)
    args.without_status_check = False
    args.command = "test"
    args.reference_year = 2026
    args.dry_run = False

    mocker.patch("codex_manager.account_status.read_status_text_from_args", return_value="Email : test@example.com\nQuota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:02 on 26 Apr)\n")
    mock_patch = mocker.patch("codex_manager.account_status.patch_metadata")

    sync_current_account_status(args)

    mock_patch.assert_called()
