from __future__ import annotations

from datetime import datetime, timezone

from codex_manager.cooldown import evaluate_records
from codex_manager.normalize import NormalizedRecord
from codex_manager.recommend import choose_best_account


def make_record(
    *,
    email: str,
    session_start_at: str,
    next_available_at: str,
    validation_status: str = "ok",
) -> NormalizedRecord:
    return NormalizedRecord(
        email=email,
        legacy_auth_filename=f"21apr_{email}_auth.json",
        legacy_quota_day_token="21apr",
        quota_end_detected_at="2026-04-14T17:55:00+00:00",
        session_start_at=session_start_at,
        next_available_at=next_available_at,
        inferred_session_duration_seconds=7200,
        proposed_archive_name=f"2026-04-14-155500-{email}-codex.tar.gz",
        validation_status=validation_status,
        validation_details="x",
        source_path=f".codex_sample/21apr_{email}_auth.json",
    )


def test_choose_best_account_prefers_ready_and_validated() -> None:
    statuses = evaluate_records(
        [
            make_record(
                email="mismatch@example.com",
                session_start_at="2026-04-10T10:00:00+00:00",
                next_available_at="2026-04-17T10:00:00+00:00",
                validation_status="mismatch",
            ),
            make_record(
                email="ok@example.com",
                session_start_at="2026-04-11T10:00:00+00:00",
                next_available_at="2026-04-18T10:00:00+00:00",
                validation_status="ok",
            ),
        ],
        now=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
    )

    recommendation = choose_best_account(statuses)
    assert recommendation.selected.email == "ok@example.com"


def test_choose_best_account_uses_earliest_unlock_when_none_ready() -> None:
    statuses = evaluate_records(
        [
            make_record(
                email="later@example.com",
                session_start_at="2026-04-19T10:00:00+00:00",
                next_available_at="2026-04-26T12:00:00+00:00",
            ),
            make_record(
                email="sooner@example.com",
                session_start_at="2026-04-19T08:00:00+00:00",
                next_available_at="2026-04-26T09:00:00+00:00",
            ),
        ],
        now=datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
    )

    recommendation = choose_best_account(statuses)
    assert recommendation.selected.email == "sooner@example.com"
