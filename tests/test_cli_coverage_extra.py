from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from codex_manager.cli import list_entries_from_args, _ensure_cloud_archive
from codex_manager.list_backups import BackupEntry
from datetime import datetime

def test_list_entries_cloud_no_cp(mocker, tmp_path, capsys):
    class Args:
        command = "list"
        backup_dir = str(tmp_path)
        cloud = True
    args = Args()

    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=None)
    with pytest.raises(SystemExit):
        list_entries_from_args(args)

    captured = capsys.readouterr()
    assert "Could not resolve Cloud" in captured.err

def test_list_entries_cloud_with_cp(mocker, tmp_path):
    class Args:
        command = "list"
        backup_dir = str(tmp_path)
        cloud = True
        email = None
        ready = False
        sort = "created_at"
    args = Args()

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)
    mocker.patch("codex_manager.cli.sync_registry_with_cloud")
    mocker.patch("codex_manager.cli.list_cloud_backups", return_value=[])

    entries = list_entries_from_args(args)
    assert entries == []

def test_list_entries_latest_per_email_both_sources(mocker, tmp_path):
    class Args:
        command = "list"
        backup_dir = str(tmp_path)
        latest_per_email = True
        cloud = False
        email = None
        ready = False
        sort = "created_at"
    args = Args()

    now = datetime.now()
    # Provide two entries for the same email but different sources
    # BackupEntry params: email, session_start_at, reset_at, created_at, source, archive_path, metadata_path, quota_text, quota_percent_left, is_expired
    entry1 = BackupEntry(
        email="test@test.com",
        session_start_at=now,
        reset_at=now,
        created_at=now,
        source="local",
        archive_path=Path(""),
        quota_text="q",
        quota_percent_left=0,
        is_expired=False
    )
    entry2 = BackupEntry(
        email="test@test.com",
        session_start_at=now,
        reset_at=now,
        created_at=now,
        source="cloud",
        archive_path=Path(""),
        quota_text="q",
        quota_percent_left=0,
        is_expired=False
    )

    mocker.patch("codex_manager.cli.list_backups", return_value=[entry1, entry2])
    # Force dir to exist
    tmp_path.joinpath("fake").write_text("fake")

    entries = list_entries_from_args(args)
    assert len(entries) == 1
    assert entries[0].source == "both"
