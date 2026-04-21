from datetime import datetime, timezone

from codex_manager.cooldown import CooldownStatus
from codex_manager.recommend import Recommendation, recommendation_to_text


def test_recommendation_to_text():
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)
    status = CooldownStatus(
        email="test@example.com",
        status="ready",
        session_start_at=now,
        next_available_at=now,
        quota_end_detected_at=now,
        validation_status="backup",
        proposed_archive_name="test.tar.gz",
        remaining_seconds=0,
    )
    rec = Recommendation(selected=status, reason="Ready now")
    out = recommendation_to_text(rec)
    assert "account: test@example.com" in out
    assert "status: ready" in out
    assert "reason: Ready now" in out
