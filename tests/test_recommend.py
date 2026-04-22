from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from codex_manager.cooldown import CooldownStatus, evaluate_records
from codex_manager.list_backups import BackupEntry
from codex_manager.recommend import choose_best_account


def make_record(
    *,
    email: str,
    session_start_at: str,
    next_available_at: str,
    ) -> BackupEntry:
    return BackupEntry(
        archive_path=Path(f"/tmp/{email}.tar.gz"),
        email=email,
        session_start_at=session_start_at,
        reset_at=next_available_at,
        created_at="2026-04-14T17:55:00+00:00",
        quota_percent_left=0,
        quota_text="[####] 0% left",
    )


def test_choose_best_account_prefers_ready_and_live_first() -> None:
    statuses = evaluate_records(
        [
            make_record(
                email="backup@example.com",
                session_start_at="2026-04-10T10:00:00+00:00",
                next_available_at="2026-04-17T10:00:00+00:00",
            ),
        ],
        now=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
    )
    statuses.append(
        CooldownStatus(
            email="live@example.com",
            status="ready",
            session_start_at=datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc),
            next_available_at=datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc),
            quota_end_detected_at=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            validation_status="live",
            proposed_archive_name="2026-04-11-100000-live@example.com-codex.tar.gz",
            remaining_seconds=0,
        )
    )

    recommendation = choose_best_account(statuses)
    assert recommendation.selected.email == "live@example.com"




@patch("codex_manager.registry.load_registry", return_value={})
def test_choose_best_account_uses_earliest_unlock_when_none_ready(mock_reg) -> None:
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
