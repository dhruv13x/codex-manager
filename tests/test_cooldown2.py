from datetime import datetime, timezone
from pathlib import Path

import pytest

from codex_manager.cooldown import CooldownStatus, evaluate_entry, statuses_to_table


def test_evaluate_entry_missing_times():
    from codex_manager.list_backups import BackupEntry
    entry = BackupEntry(
        archive_path=Path("path"),
        email="a@b.com",
        session_start_at="unknown",
        reset_at="unknown",
        created_at="unknown",
        quota_percent_left=None,
        quota_text="q"
    )
    with pytest.raises(ValueError):
        evaluate_entry(entry)

def test_evaluate_entry_cooldown():
    from codex_manager.list_backups import BackupEntry
    now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    entry = BackupEntry(
        archive_path=Path("path"),
        email="a@b.com",
        session_start_at="2026-04-18T10:00:00+00:00",
        reset_at="2026-04-25T10:00:00+00:00",
        created_at="2026-04-19T10:00:00+00:00",
        quota_percent_left=0,
        quota_text="q"
    )
    res = evaluate_entry(entry, now=now)
    assert res.status == "cooldown"

def test_evaluate_entry_ready():
    from codex_manager.list_backups import BackupEntry
    now = datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc)
    entry = BackupEntry(
        archive_path=Path("path"),
        email="a@b.com",
        session_start_at="2026-04-18T10:00:00+00:00",
        reset_at="2026-04-25T10:00:00+00:00",
        created_at="2026-04-19T10:00:00+00:00",
        quota_percent_left=0,
        quota_text="q"
    )
    res = evaluate_entry(entry, now=now)
    assert res.status == "ready"

def test_statuses_to_table():
    s1 = CooldownStatus("a@b.com", "ready", datetime.now(), datetime.now(), datetime.now(), "valid", "archive", 0)
    s2 = CooldownStatus("b@b.com", "cooldown", datetime.now(), datetime.now(), datetime.now(), "valid", "archive2", 100)
    table = statuses_to_table([s1, s2])
    assert table is not None
