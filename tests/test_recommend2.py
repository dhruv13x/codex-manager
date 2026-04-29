from __future__ import annotations

from datetime import datetime, timezone
from codex_manager.cooldown import CooldownStatus
from codex_manager.recommend import choose_best_account


def test_choose_best_account_prefers_non_expired():
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    
    # Ready but expired
    expired_ready = CooldownStatus(
        email="expired@example.com",
        status="ready",
        session_start_at=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
        next_available_at=datetime(2026, 4, 29, 10, 0, tzinfo=timezone.utc),
        quota_end_detected_at=datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive1",
        remaining_seconds=0,
        is_expired=True
    )
    
    # Ready and not expired
    not_expired_ready = CooldownStatus(
        email="ready@example.com",
        status="ready",
        session_start_at=datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc),
        next_available_at=datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
        quota_end_detected_at=datetime(2026, 4, 22, 13, 0, tzinfo=timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive2",
        remaining_seconds=0,
        is_expired=False
    )
    
    # Expired should be ranked lower even if it has earlier session_start_at
    recommendation = choose_best_account([expired_ready, not_expired_ready])
    assert recommendation.selected.email == "ready@example.com"
    assert "but requires re-login" not in recommendation.reason


def test_choose_best_account_picks_expired_if_only_ready_option():
    expired_ready = CooldownStatus(
        email="expired@example.com",
        status="ready",
        session_start_at=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
        next_available_at=datetime(2026, 4, 29, 10, 0, tzinfo=timezone.utc),
        quota_end_detected_at=datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive1",
        remaining_seconds=0,
        is_expired=True
    )
    
    cooldown_not_expired = CooldownStatus(
        email="cooldown@example.com",
        status="cooldown",
        session_start_at=datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
        next_available_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
        quota_end_detected_at=datetime(2026, 4, 25, 11, 0, tzinfo=timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive2",
        remaining_seconds=1000,
        is_expired=False
    )
    
    # Ready (expired) is better than Cooldown (not expired)
    recommendation = choose_best_account([expired_ready, cooldown_not_expired])
    assert recommendation.selected.email == "expired@example.com"
    assert "requires re-login" in recommendation.reason
