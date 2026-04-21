import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codex_manager.cli import sync_current_account_status


@pytest.fixture
def mock_args(tmp_path):
    args = MagicMock()
    args.dest_dir = str(tmp_path / "codex")
    args.backup_dir = str(tmp_path / "backups")
    args.without_status_check = False
    args.cloud = False
    args.command = "use"
    
    # Setup codex home
    codex_home = Path(args.dest_dir)
    codex_home.mkdir(parents=True)
    (codex_home / "auth.json").write_text(json.dumps({"email": "test@example.com"}), encoding="utf-8")
    
    # Setup backups dir
    backups_dir = Path(args.backup_dir)
    backups_dir.mkdir(parents=True)
    
    return args

def test_sync_current_account_status_with_bypass(mock_args):
    mock_args.without_status_check = True
    
    # Prepare a "latest" metadata to be patched
    email = "test@example.com"
    backups_dir = Path(mock_args.backup_dir)
    archive_name = f"2026-04-20-120000-{email}-codex.tar.gz"
    
    # Create the archive file (empty is fine)
    (backups_dir / archive_name).write_text("fake archive", encoding="utf-8")
    
    metadata_name = archive_name.replace(".tar.gz", ".metadata.json")
    metadata_path = backups_dir / metadata_name
    
    initial_metadata = {
        "email": email,
        "reset_at": "2026-04-20T12:00:00+00:00",
        "archive_name": archive_name
    }
    metadata_path.write_text(json.dumps(initial_metadata), encoding="utf-8")
    
    # We also need a "latest" symlink for list_backups to find it easily 
    # (though list_backups scans the dir)
    (backups_dir / f"{email}-latest-codex.tar.gz").symlink_to(archive_name)

    now = datetime.now().astimezone()
    with patch("codex_manager.account_status.datetime") as mock_datetime:
        mock_datetime.now.return_value.astimezone.return_value = now
        sync_current_account_status(mock_args)
    
    # Verify metadata was updated with +7 days
    updated_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    
    expected_reset = (now + timedelta(days=7)).isoformat()
    # Allowing some mismatch in micro-seconds if any, but isoformat should be consistent
    assert updated_metadata["reset_at"] == expected_reset
    assert "Estimated +7 days cooldown" in updated_metadata["quota_text"]


def test_sync_current_account_status_with_bypass_creates_reset_based_metadata_name(mock_args):
    mock_args.without_status_check = True

    fixed_now = datetime(2026, 4, 21, 11, 18, 38).astimezone()

    with patch("codex_manager.account_status.datetime") as mock_datetime:
        mock_datetime.now.return_value.astimezone.return_value = fixed_now
        sync_current_account_status(mock_args)

    expected_reset = fixed_now + timedelta(days=7)
    expected_name = (
        f"{expected_reset.strftime('%Y-%m-%d-%H%M%S')}-test@example.com-codex.metadata.json"
    )
    metadata_path = Path(mock_args.backup_dir) / expected_name

    assert metadata_path.exists()
    created_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert created_metadata["archive_name"] == expected_name.replace(".metadata.json", ".tar.gz")
    assert created_metadata["reset_at"] == expected_reset.isoformat()
    assert created_metadata["session_start_at"] == fixed_now.isoformat()

def test_sync_current_account_status_failure_instructions(mock_args, capsys):
    mock_args.without_status_check = False
    
    # Mock status capture failure
    with patch("codex_manager.account_status.read_status_text_from_args", side_effect=Exception("Timeout")):
        with pytest.raises(SystemExit) as excinfo:
            sync_current_account_status(mock_args)
        
        assert excinfo.value.code == 1
        
    captured = capsys.readouterr()
    assert "Next-Gen Safety Protocol" in captured.out
    assert "--without-status-check" in captured.out
