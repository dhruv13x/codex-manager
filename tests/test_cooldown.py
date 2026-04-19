from __future__ import annotations

from datetime import datetime, timezone

from codex_manager.cooldown import evaluate_record, evaluate_records, format_remaining, CooldownStatus
from codex_manager.normalize import NormalizedRecord


def make_record(next_available_at: str, email: str = "a@example.com") -> NormalizedRecord:
    return NormalizedRecord(
        email=email,
        legacy_auth_filename="21apr_a@example.com_auth.json",
        legacy_quota_day_token="21apr",
        quota_end_detected_at="2026-04-14T17:55:00+00:00",
        session_start_at="2026-04-14T15:55:00+00:00",
        next_available_at=next_available_at,
        inferred_session_duration_seconds=7200,
        proposed_archive_name=f"2026-04-14-155500-{email}-codex.tar.gz",
        validation_status="ok",
        validation_details="ok",
        source_path=".codex_sample/21apr_a@example.com_auth.json",
    )


def test_evaluate_record_ready() -> None:
    record = make_record("2026-04-20T15:55:00+00:00")
    status = evaluate_record(record, now=datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc))
    assert status.status == "ready"
    assert status.remaining_seconds == 0


def test_evaluate_record_cooldown() -> None:
    record = make_record("2026-04-21T18:00:00+00:00")
    status = evaluate_record(record, now=datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc))
    assert status.status == "cooldown"
    assert status.remaining_seconds == 7200


def test_evaluate_records_sorts_ready_first() -> None:
    ready = make_record("2026-04-20T15:55:00+00:00", email="ready@example.com")
    locked = make_record("2026-04-22T15:55:00+00:00", email="locked@example.com")
    statuses = evaluate_records(
        [locked, ready],
        now=datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc),
    )
    assert statuses[0].email == "ready@example.com"
    assert statuses[1].email == "locked@example.com"


def test_evaluate_records_merges_live_status() -> None:
    now = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    record1 = NormalizedRecord(
        email="a@example.com",
        legacy_auth_filename="test.json",
        legacy_quota_day_token="19apr",
        quota_end_detected_at="2026-04-12T12:00:00+00:00",
        session_start_at="2026-04-12T10:00:00+00:00",
        next_available_at="2026-04-19T10:00:00+00:00",
        inferred_session_duration_seconds=7200,
        proposed_archive_name="2026-04-12-100000-a@example.com-codex.tar.gz",
        validation_status="ok",
        validation_details="ok",
        source_path=".codex_sample/19apr_a@example.com_auth.json",
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

    statuses = evaluate_records([record1], now=now, live_status=live_status)
    assert len(statuses) == 1
    assert statuses[0].validation_status == "live"
    assert statuses[0].next_available_at.day == 20


def test_format_remaining() -> None:
    assert format_remaining(0) == "now"
    assert format_remaining(5400) == "1h 30m"
