from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from codex_manager.restore import (
    latest_backup_archive,
    load_metadata_for_archive,
    move_existing_target,
    resolve_archive_path,
    restore_result_to_text,
    validate_archive_contents,
)


def test_latest_backup_archive_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        latest_backup_archive(tmp_path / "does_not_exist")

def test_latest_backup_archive_empty(tmp_path):
    d = tmp_path / "b"
    d.mkdir()
    with pytest.raises(FileNotFoundError):
        latest_backup_archive(d)

def test_resolve_archive_path_from_archive(tmp_path):
    f = tmp_path / "a-codex.tar.gz"
    f.write_text("x")
    args = SimpleNamespace(from_archive=str(f))
    assert resolve_archive_path(args) == f.resolve()

def test_resolve_archive_path_email(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    f = d / "foo-latest-codex.tar.gz"
    f.write_text("x")
    args = SimpleNamespace(from_archive=None, email="foo", backup_dir=str(d))
    assert resolve_archive_path(args) == f.resolve()

def test_resolve_archive_path_missing(tmp_path):
    args = SimpleNamespace(from_archive=str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError):
        resolve_archive_path(args)

@patch("codex_manager.restore.tarfile.open")
def test_load_metadata_for_archive_missing(mock_tar_open, tmp_path):
    f = tmp_path / "a-codex.tar.gz"
    f.write_text("x")

    mock_tar = MagicMock()
    mock_tar.getmember.side_effect = KeyError("not found")
    mock_tar_open.return_value.__enter__.return_value = mock_tar

    with pytest.raises(FileNotFoundError):
        load_metadata_for_archive(f)

@patch("codex_manager.restore.tarfile.open")
def test_validate_archive_contents_fail(mock_tar_open, tmp_path):
    f = tmp_path / "a-codex.tar.gz"
    f.write_text("x")

    mock_tar = MagicMock()
    mock_tar.getnames.return_value = ["other"]
    mock_tar_open.return_value.__enter__.return_value = mock_tar

    with pytest.raises(ValueError):
        validate_archive_contents(f)

def test_move_existing_target_none(tmp_path):
    assert move_existing_target(tmp_path / "missing") is None

def test_restore_result_to_text():
    res = restore_result_to_text(Path("a"), Path("b"), {"email": "c", "session_start_at": "d", "reset_at": "e", "quota_text": "f"}, Path("g"), dry_run=True)
    try:
        import io

        from rich.console import Console
        console = Console(file=io.StringIO(), force_terminal=False)
        console.print(res)
        res_str = console.file.getvalue()
    except ImportError:
        res_str = str(res)
    assert "dry-run" in res_str
    assert "backed_up_existing_to" in res_str
