from __future__ import annotations
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from codex_manager.cli import handle_backup, handle_profile, handle_status

def test_handle_backup_cloud_dry_run(mocker, capsys) -> None:
    class Args:
        pass
    args = Args()
    args.cloud = True
    args.dry_run = True

    archive_path = Path("fake-archive.tar.gz")
    metadata_path = Path("fake-archive.metadata.json")
    metadata = {"email": "test@example.com", "session_start_at": "1", "reset_at": "1", "quota_text": "1"}

    mocker.patch("codex_manager.cli.perform_backup", return_value=(archive_path, metadata_path, metadata))

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)
    mock_sync = mocker.patch("codex_manager.cli.sync_registry_with_cloud")

    handle_backup(args)

    captured = capsys.readouterr()
    assert "Would upload to Cloud: fake-archive.tar.gz" in captured.out
    mock_sync.assert_called_once_with(mock_cp, dry_run=True)

def test_handle_profile_dry_run(mocker, tmp_path: Path) -> None:
    class Args:
        pass
    args = Args()
    args.action = "export"
    args.file = str(tmp_path / "test.tar.gz")
    args.dry_run = True

    mock_export = mocker.patch("codex_manager.cli.export_profile")

    handle_profile(args)

    mock_export.assert_called_once()
    assert mock_export.call_args.kwargs["dry_run"] is True

def test_handle_status_dry_run(mocker) -> None:
    class Args:
        pass
    args = Args()
    args.dry_run = True
    args.reference_year = 2026
    args.source_dir = None
    args.input_file = None
    args.status_command = None
    args.tmux_session_name = None
    args.codex_command = None
    args.tmux_cols = 120
    args.tmux_rows = 40
    args.startup_timeout_seconds = 20
    args.status_timeout_seconds = 20

    mocker.patch("codex_manager.cli._read_status_command_input", return_value="Email : letsmaildhruv@gmail.com\nQuota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:02 on 26 Apr)\n")
    mock_patch = mocker.patch("codex_manager.cli.patch_metadata")

    handle_status(args)

    mock_patch.assert_called_once()
    assert mock_patch.call_args.kwargs["dry_run"] is True
