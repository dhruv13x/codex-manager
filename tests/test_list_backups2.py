import json
from pathlib import Path
from unittest.mock import MagicMock

from codex_manager.list_backups import (
    BackupEntry,
    entries_to_table,
    list_backups,
    list_cloud_backups,
)


def test_list_backups_empty(tmp_path):
    assert list_backups(tmp_path) == []

def test_list_backups_basic(tmp_path):
    bdir = tmp_path / "backups"
    bdir.mkdir()
    f1 = bdir / "2026-04-19-100200-a@b.com-codex.tar.gz"
    f1.write_text("dummy")
    m1 = bdir / "2026-04-19-100200-a@b.com-codex.metadata.json"
    m1.write_text(json.dumps({"email": "a@b.com", "reset_at": "2026-04-20T10:00:00+00:00", "created_at": "2026-04-19T10:00:00+00:00", "session_start_at": "2026-04-13T10:00:00+00:00"}))

    entries = list_backups(bdir)
    assert len(entries) == 1
    assert entries[0].email == "a@b.com"

    # filter email
    assert len(list_backups(bdir, email="other")) == 0

def test_list_cloud_backups():
    cp = MagicMock()
    file_obj = MagicMock()
    file_obj.name = "2026-04-19-100200-a@b.com-codex.metadata.json"
    cp.list_files.return_value = [file_obj]

    meta_json = json.dumps({"email": "a@b.com", "reset_at": "2026-04-20T10:00:00+00:00", "created_at": "2026-04-19T10:00:00+00:00", "session_start_at": "2026-04-13T10:00:00+00:00", "archive_path": "path"})
    def mock_download(name, path):
        path.write_text(meta_json)
    cp.download_file.side_effect = mock_download

    entries = list_cloud_backups(cp)
    assert len(entries) == 1
    assert entries[0].email == "a@b.com"

    entries2 = list_cloud_backups(cp, latest_per_email=True)
    assert len(entries2) == 1

def test_entries_to_table():
    entry = BackupEntry(
        archive_path=Path("2026-04-19-100200-a@b.com-codex.tar.gz"),
        email="a@b.com",
        session_start_at="2026-04-13T10:00:00+00:00",
        reset_at="2026-04-20T10:00:00+00:00",
        created_at="2026-04-19T10:00:00+00:00",
        quota_text="10% left",
        quota_percent_left=10
    )
    records = [entry]
    table = entries_to_table(records)
    assert table is not None
