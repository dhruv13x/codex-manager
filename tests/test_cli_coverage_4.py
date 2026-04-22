from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codex_manager.cli import handle_backup, handle_status
from codex_manager.status import TokenExpiredError


def test_handle_status_token_expired_auth_json(mocker, tmp_path, capsys):
    class Args:
        source_dir = str(tmp_path)
        reference_year = 2026
        dry_run = True
    args = Args()

    (tmp_path / "auth.json").write_text(json.dumps({"email": "test@test.com"}))

    mocker.patch("codex_manager.cli._read_status_command_input", side_effect=TokenExpiredError("expired", "raw"))
    mocker.patch("codex_manager.cli.parse_live_status_text", side_effect=Exception("could not parse"))
    mock_patch = mocker.patch("codex_manager.cli.patch_metadata")

    with pytest.raises(SystemExit):
        handle_status(args)

    mock_patch.assert_called_once()
    assert mock_patch.call_args.kwargs["email"] == "test@test.com"

def test_handle_backup_cloud_no_dry_run(mocker, capsys):
    class Args:
        cloud = True
        dry_run = False

    args = Args()
    archive_path = Path("fake-archive.tar.gz")
    metadata_path = Path("fake-archive.metadata.json")
    metadata = {"email": "test@example.com", "session_start_at": "1", "reset_at": "1", "quota_text": "1"}

    mocker.patch("codex_manager.cli.perform_backup", return_value=(archive_path, metadata_path, metadata))

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)
    mock_sync = mocker.patch("codex_manager.cli.sync_registry_with_cloud")

    handle_backup(args)

    mock_cp.upload_file.assert_called()
    mock_sync.assert_called_once_with(mock_cp)
    captured = capsys.readouterr()
    assert "Cloud upload complete" in captured.out

def test_handle_backup_cloud_no_cp(mocker, capsys):
    class Args:
        cloud = True
        dry_run = False

    args = Args()
    archive_path = Path("fake-archive.tar.gz")
    metadata_path = Path("fake-archive.metadata.json")
    metadata = {"email": "test@example.com", "session_start_at": "1", "reset_at": "1", "quota_text": "1"}

    mocker.patch("codex_manager.cli.perform_backup", return_value=(archive_path, metadata_path, metadata))
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=None)

    handle_backup(args)

    captured = capsys.readouterr()
    assert "Could not resolve Cloud" in captured.err
