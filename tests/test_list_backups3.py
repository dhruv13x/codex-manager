import json
from unittest.mock import MagicMock, patch

import pytest

from codex_manager.list_backups import (
    build_backup_entry,
    entries_to_table,
    iter_backup_archives,
    list_cloud_backups,
)


def test_list_cloud_backups_empty():
    cp = MagicMock()
    cp.list_files.return_value = []
    assert list_cloud_backups(cp) == []

def test_list_cloud_backups_error():
    cp = MagicMock()
    file_obj = MagicMock()
    file_obj.name = "2026-04-19-100200-a@b.com-codex.metadata.json"
    cp.list_files.return_value = [file_obj]

    def mock_download(name, path):
        raise Exception("err")
    cp.download_file.side_effect = mock_download

    assert list_cloud_backups(cp) == []

def test_list_cloud_backups_email_ready_sort():
    cp = MagicMock()
    f1 = MagicMock()
    f1.name = "2026-04-19-100200-a@b.com-codex.metadata.json"
    f2 = MagicMock()
    f2.name = "2026-04-19-100200-other@b.com-codex.metadata.json"
    f3 = MagicMock()
    f3.name = "invalid.metadata.json"
    f4 = MagicMock()
    f4.name = "notready.metadata.json"

    cp.list_files.return_value = [f1, f2, f3, f4]

    def mock_download(name, path):
        if "other" in name:
            path.write_text(json.dumps({"email": "other@b.com", "reset_at": "2026-04-20T10:00:00+00:00", "session_start_at": "a"}))
        elif "invalid" in name:
            path.write_text(json.dumps({"email": "a@b.com", "reset_at": "unknown"}))
        elif "notready" in name:
            path.write_text(json.dumps({"email": "a@b.com", "reset_at": "2030-04-20T10:00:00+00:00", "session_start_at": "b"}))
        else:
            path.write_text(json.dumps({"email": "a@b.com", "reset_at": "2020-04-20T10:00:00+00:00", "session_start_at": "c"}))

    cp.download_file.side_effect = mock_download

    entries = list_cloud_backups(cp, email="a@b.com", ready=True, sort_by="reset_at")
    assert len(entries) == 1
    assert entries[0].email == "a@b.com"

    entries = list_cloud_backups(cp, ready=True, sort_by="session_start_at")
    assert len(entries) == 2

def test_entries_to_table():
    from datetime import datetime

    from codex_manager.cooldown import CooldownStatus
    s1 = CooldownStatus("a@b.com", "ready", datetime.now(), datetime.now(), datetime.now(), "valid", "archive", 0)
    object.__setattr__(s1, 'quota_percent_left', 10)
    object.__setattr__(s1, 'reset_at', "reset_at")

    s2 = CooldownStatus("b@b.com", "cooldown", datetime.now(), datetime.now(), datetime.now(), "valid", "archive2", 100)
    object.__setattr__(s2, 'quota_percent_left', None)
    object.__setattr__(s2, 'reset_at', "reset_at")

    table = entries_to_table([s1, s2])
    assert table is not None

def test_iter_backup_archives(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    f1 = d / "test-codex.tar.gz"
    f1.write_text("x")
    f2 = d / "other.txt"
    f2.write_text("x")
    f3 = d / "symlink-codex.tar.gz"
    f3.symlink_to(f1.name) # symlinks are skipped but tested here just in case

    res = list(iter_backup_archives(d))
    assert len(res) == 2

@patch("codex_manager.list_backups.load_metadata_for_archive")
def test_build_backup_entry(mock_load, tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    f1 = d / "test-codex.tar.gz"

    mock_load.return_value = {"email": "a"}
    entry = build_backup_entry(f1)
    assert entry.email == "a"

    # Missing metadata
    mock_load.side_effect = FileNotFoundError
    with pytest.raises(FileNotFoundError):
        build_backup_entry(f1)
