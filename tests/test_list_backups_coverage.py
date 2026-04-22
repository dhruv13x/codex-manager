from __future__ import annotations

from unittest.mock import MagicMock

from codex_manager.list_backups import build_backup_entry, list_backups, list_cloud_backups


def test_list_backups_sort_session(mocker, tmp_path):
    b1 = MagicMock()
    b1.email = "e1"
    b1.session_start_at = "1"
    b1.created_at = "1"

    b2 = MagicMock()
    b2.email = "e2"
    b2.session_start_at = "2"
    b2.created_at = "2"

    mocker.patch("codex_manager.list_backups.build_backup_entry", side_effect=[b1, b2])
    mocker.patch("codex_manager.list_backups.iter_backup_archives", return_value=["a", "b"])

    res = list_backups(tmp_path, sort_by="session_start_at")
    assert res == [b2, b1]

def test_list_backups_ready_unknown_and_valueerror(mocker, tmp_path):
    b1 = MagicMock()
    b1.email = "e1"
    b1.reset_at = "unknown"

    b2 = MagicMock()
    b2.email = "e2"
    b2.reset_at = "invalid_format"

    mocker.patch("codex_manager.list_backups.build_backup_entry", side_effect=[b1, b2])
    mocker.patch("codex_manager.list_backups.iter_backup_archives", return_value=["a", "b"])

    res = list_backups(tmp_path, ready=True)
    assert res == []

def test_list_cloud_backups_ready_unknown_and_valueerror(mocker):
    mock_cp = MagicMock()
    mock_file1 = MagicMock()
    mock_file1.name = "1.metadata.json"
    mock_file2 = MagicMock()
    mock_file2.name = "2.metadata.json"
    mock_cp.list_files.return_value = [mock_file1, mock_file2]

    def dl_file(remote, local):
        if "1" in remote:
            local.write_text('{"reset_at": "unknown"}')
        else:
            local.write_text('{"reset_at": "invalid_date"}')

    mock_cp.download_file = dl_file

    res = list_cloud_backups(mock_cp, ready=True)
    assert res == []

def test_list_cloud_backups_sort_session(mocker):
    mock_cp = MagicMock()
    mock_file1 = MagicMock()
    mock_file1.name = "1.metadata.json"
    mock_file2 = MagicMock()
    mock_file2.name = "2.metadata.json"
    mock_cp.list_files.return_value = [mock_file1, mock_file2]

    def dl_file(remote, local):
        if "1" in remote:
            local.write_text('{"session_start_at": "1", "created_at": "1"}')
        else:
            local.write_text('{"session_start_at": "2", "created_at": "2"}')

    mock_cp.download_file = dl_file

    res = list_cloud_backups(mock_cp, sort_by="session_start_at")
    assert res[0].session_start_at == "2"

def test_build_backup_entry_buddy(mocker, tmp_path):
    (tmp_path / "test.metadata.json").write_text('{}')
    (tmp_path / "test.tar.gz").write_text('')
    mocker.patch("codex_manager.list_backups.load_metadata_for_archive", return_value={})
    res = build_backup_entry(tmp_path / "test.metadata.json")
    assert res.archive_path == tmp_path / "test.tar.gz"
