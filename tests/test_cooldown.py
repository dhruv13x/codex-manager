from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from codex_manager.cooldown import CooldownStatus, evaluate_entry, evaluate_records, format_remaining
from codex_manager.list_backups import BackupEntry


def make_entry(reset_at: str, email: str = "a@example.com") -> BackupEntry:
    return BackupEntry(
        archive_path=Path(f"/tmp/{email}.tar.gz"),
        email=email,
        session_start_at="2026-04-14T15:55:00+00:00",
        reset_at=reset_at,
        created_at="2026-04-14T17:55:00+00:00",
        quota_percent_left=0,
        quota_text="[####] 0% left",
    )


def test_evaluate_record_ready() -> None:
    entry = make_entry("2026-04-20T15:55:00+00:00")
    status = evaluate_entry(entry, now=datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc))
    assert status.status == "ready"
    assert status.remaining_seconds == 0


def test_evaluate_record_cooldown() -> None:
    entry = make_entry("2026-04-21T18:00:00+00:00")
    status = evaluate_entry(entry, now=datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc))
    assert status.status == "cooldown"
    assert status.remaining_seconds == 7200


def test_evaluate_records_sorts_ready_first() -> None:
    ready = make_entry("2026-04-20T15:55:00+00:00", email="ready@example.com")
    locked = make_entry("2026-04-22T15:55:00+00:00", email="locked@example.com")
    statuses = evaluate_records(
        [locked, ready],
        now=datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc),
    )
    assert statuses[0].email == "ready@example.com"
    assert statuses[1].email == "locked@example.com"


def test_evaluate_records_merges_live_status() -> None:
    now = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    entry1 = BackupEntry(
        archive_path=Path("/tmp/a@example.com.tar.gz"),
        email="a@example.com",
        session_start_at="2026-04-12T10:00:00+00:00",
        reset_at="2026-04-19T10:00:00+00:00",
        created_at="2026-04-12T12:00:00+00:00",
        quota_percent_left=0,
        quota_text="[####] 0% left",
    )

    live_status = CooldownStatus(
        email="a@example.com",
        status="cooldown",
        session_start_at=datetime(2026, 4, 13, 10, 0, 0, tzinfo=timezone.utc),
        next_available_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc),
        quota_end_detected_at=datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc),
        validation_status="live",
        proposed_archive_name="2026-04-13-100000-a@example.com-codex.tar.gz",
        remaining_seconds=1000,
    )

    statuses = evaluate_records([entry1], now=now, live_status=live_status)
    assert len(statuses) == 1
    assert statuses[0].validation_status == "live"
    assert statuses[0].next_available_at.day == 20


def test_format_remaining() -> None:
    assert format_remaining(0) == "now"
    assert format_remaining(5400) == "1h 30m"
