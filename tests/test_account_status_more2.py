from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from codex_manager.account_status import patch_metadata


def test_patch_metadata_local_create_fail(mocker, tmp_path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    email = "test@example.com"
    archive_name = f"2026-04-19-100200-{email}-codex.metadata.json"

    # Do not create existing metadata file
    class Args:
        pass

    args = Args()
    args.backup_dir = str(backup_dir)
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    mocker.patch("codex_manager.account_status.update_registry_entry")

    # Mock write_text to raise an exception
    mocker.patch("codex_manager.account_status.Path.write_text", side_effect=Exception("some error"))

    patch_metadata(email, reset_at=now, args=args)

    captured = capsys.readouterr()
    assert "Failed to create local metadata" in captured.out

def test_patch_metadata_cloud_download_update_fail(mocker, tmp_path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    class Args:
        pass

    args = Args()
    args.backup_dir = str(backup_dir)
    args.cloud = True
    email = "test@example.com"
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    mocker.patch("codex_manager.account_status.update_registry_entry")
    mocker.patch("codex_manager.account_status.sync_registry_with_cloud")

    mock_cp = MagicMock()
    mock_entry = MagicMock()
    mock_entry.archive_path.name = "fake.tar.gz"
    mocker.patch("codex_manager.account_status.list_cloud_backups", return_value=[mock_entry])
    mocker.patch("codex_manager.account_status.get_cloud_provider", return_value=mock_cp)

    mock_cp.download_file.side_effect = Exception("download failed")

    patch_metadata(email, reset_at=now, args=args, dry_run=False)

    captured = capsys.readouterr()
    assert "Failed to patch cloud metadata" in captured.out

def test_patch_metadata_cloud_no_cp(mocker, tmp_path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    class Args:
        pass

    args = Args()
    args.backup_dir = str(backup_dir)
    args.cloud = True
    email = "test@example.com"
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    mocker.patch("codex_manager.account_status.update_registry_entry")
    mocker.patch("codex_manager.account_status.get_cloud_provider", return_value=None)

    patch_metadata(email, reset_at=now, args=args, dry_run=False)

    captured = capsys.readouterr()
    assert "Cloud update requested but credentials not resolved" in captured.out
