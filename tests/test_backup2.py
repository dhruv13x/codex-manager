import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from codex_manager.backup import backup_result_to_text, perform_backup, read_status_text_from_args


def test_read_status_text_from_args_status_file(tmp_path):
    f = tmp_path / "status.txt"
    f.write_text("status")
    args = SimpleNamespace(status_file=str(f))
    assert read_status_text_from_args(args) == "status"

def test_read_status_text_from_args_command(tmp_path):
    args = SimpleNamespace(status_file=None, status_command="echo 'status'")
    assert read_status_text_from_args(args).strip() == "status"

def test_read_status_text_from_args_command_fail(tmp_path):
    args = SimpleNamespace(
        status_file=None,
        status_command="python3 -c 'import sys; sys.exit(1)'",
    )
    with pytest.raises(RuntimeError):
        read_status_text_from_args(args)

@patch("codex_manager.backup.capture_tmux_status_text")
def test_read_status_text_from_args_tmux(mock_capture):
    mock_capture.return_value = "status"
    args = SimpleNamespace(status_file=None, status_command=None, tmux_session_name="a", codex_command="b", tmux_cols=1, tmux_rows=1, startup_timeout_seconds=1.0, status_timeout_seconds=1.0)
    assert read_status_text_from_args(args) == "status"

def test_perform_backup_no_source(tmp_path):
    args = SimpleNamespace(source_dir=str(tmp_path / "does_not_exist"))
    with pytest.raises(FileNotFoundError):
        perform_backup(args)

def test_perform_backup_force(tmp_path):
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    status_file = tmp_path / "status.txt"
    status_file.write_text("Email: test@gmail.com\nQuota: [░] 0% left (resets 10:02 on 26 Apr)")

    args = SimpleNamespace(
        source_dir=str(source_dir),
        backup_dir=str(backup_dir),
        status_file=str(status_file),
        reference_year=2026,
        dry_run=False,
        force=False,
        prune_first=False,
        auth_only=False,
        include_tmp=False
    )

    # First backup should succeed
    archive, _, _ = perform_backup(args)
    assert archive.exists()

    # Second backup should also succeed without force (since we now auto-overwrite to protect rotated tokens)
    perform_backup(args)
    assert archive.exists()

def test_backup_result_to_text():
    res = backup_result_to_text(Path("archive"), Path("meta"), {"email": "a", "session_start_at": "b", "reset_at": "c", "quota_text": "d"}, dry_run=True)
    assert "dry-run" in res


@patch("codex_manager.backup.read_status_text_from_args")
def test_perform_backup_fallback_expired(mock_read, tmp_path):
    from codex_manager.status import TokenExpiredError
    mock_read.side_effect = TokenExpiredError("Expired token test", "expired output")

    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    
    # Write auth.json with mocked tokens
    auth_data = {
        "tokens": {
            # Base64 encoded: {"email": "fallback-test@gmail.com"}
            "id_token": "header.eyJlbWFpbCI6ICJmYWxsYmFjay10ZXN0QGdtYWlsLmNvbSJ9.signature"
        }
    }
    (source_dir / "auth.json").write_text(json.dumps(auth_data))

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    args = SimpleNamespace(
        source_dir=str(source_dir),
        backup_dir=str(backup_dir),
        status_file=None,
        status_command=None,
        reference_year=2026,
        dry_run=False,
        force=False,
        prune_first=False,
        auth_only=False,
        include_tmp=False,
        without_status_check=False
    )

    # perform_backup should NOT crash; it should fall back to offline identification and save!
    archive_path, metadata_path, metadata = perform_backup(args)

    assert archive_path.exists()
    assert metadata_path.exists()
    assert metadata["is_expired"] is True
    assert metadata["status_error"] == "TokenExpiredError"
    
    # We also verify that the auth-only backup was created at the correct Split Store location
    auth_archive = backup_dir / "auth" / "fallback-test@gmail.com" / "latest.tar.gz"
    auth_metadata = backup_dir / "auth" / "fallback-test@gmail.com" / "latest.metadata.json"
    assert auth_archive.exists()
    assert auth_metadata.exists()

