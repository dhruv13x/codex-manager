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
    args = SimpleNamespace(status_file=None, status_command="exit 1")
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

    # Second should fail without force
    with pytest.raises(FileExistsError):
        perform_backup(args)

    # Third should succeed with force
    args.force = True
    perform_backup(args)

def test_backup_result_to_text():
    res = backup_result_to_text(Path("archive"), Path("meta"), {"email": "a", "session_start_at": "b", "reset_at": "c", "quota_text": "d"}, dry_run=True)
    from codex_manager.rich_utils import RICH_AVAILABLE
    if RICH_AVAILABLE:
        assert hasattr(res, "columns")
    else:
        assert "dry-run" in res
