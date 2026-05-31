import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from codex_manager.cooldown import (
    evaluate_entry,
    format_auth_state,
    format_quota_display,
    statuses_to_table,
)
from codex_manager.list_backups import BackupEntry
from codex_manager.utils import extract_email_from_auth_json, extract_jwt_details


def make_jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def encode(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode(header)}.{encode(payload)}."


def test_extract_jwt_details_captures_sanitized_auth_metadata(tmp_path: Path) -> None:
    id_token = make_jwt(
        {
            "auth_provider": "google",
            "auth_time": 1780198800,
            "email": "user@example.com",
            "email_verified": True,
            "exp": 1780202533,
            "iat": 1780198933,
            "jti": "do-not-store",
            "sid": "do-not-store",
            "name": "User",
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "acct-123",
                "chatgpt_plan_type": "plus",
                "chatgpt_subscription_active_until": "2026-07-01T00:00:00+00:00",
                "chatgpt_subscription_last_checked": "2026-05-31T00:00:00+00:00",
                "chatgpt_user_id": "user-123",
                "organizations": [
                    {
                        "id": "org-123",
                        "title": "Personal",
                        "role": "owner",
                        "is_default": True,
                    }
                ],
            },
        }
    )
    access_token = make_jwt(
        {
            "exp": 1780800000,
            "iat": 1780199000,
            "https://api.openai.com/profile": {"email": "profile@example.com"},
        }
    )
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps({"tokens": {"id_token": id_token, "access_token": access_token}}),
        encoding="utf-8",
    )

    details = extract_jwt_details(auth_path)

    assert extract_email_from_auth_json(auth_path) == "user@example.com"
    assert details["plan_type"] == "plus"
    assert details["auth_provider"] == "google"
    assert details["chatgpt_account_id"] == "acct-123"
    assert details["chatgpt_user_id"] == "user-123"
    assert details["organizations"] == [
        {"id": "org-123", "title": "Personal", "role": "owner", "is_default": True}
    ]
    assert details["id_token_expires_at"] is not None
    assert details["access_token_expires_at"] is not None
    assert details["auth_expires_at"] == details["access_token_expires_at"]
    assert "jti" not in details
    assert "sid" not in details


def test_cooldown_uses_effective_auth_expiration() -> None:
    entry = BackupEntry(
        archive_path=Path("backup.tar.gz"),
        email="user@example.com",
        session_start_at="2026-05-31T09:12:00+05:30",
        reset_at="2026-06-07T09:12:00+05:30",
        created_at="2026-05-31T10:03:29+05:30",
        quota_percent_left=96,
        quota_text="96% left",
        plan_type="free",
        access_token_expires_at="2026-06-20T10:00:00+05:30",
        auth_expires_at="2026-06-20T10:00:00+05:30",
    )

    status = evaluate_entry(entry)
    table = statuses_to_table([status])

    assert "Plan" not in table
    assert "FREE" not in table
    assert "(free)" not in table
    assert "Auth State" in table
    assert "Valid" in table
    assert "Session Start" not in table
    assert "Reset At" not in table


def test_format_auth_state_relative_states() -> None:
    now = datetime(2026, 5, 31, 10, 0, tzinfo=timezone.utc)

    assert format_auth_state(None, now=now) == "Unknown"
    assert format_auth_state("not-a-date", now=now) == "Unknown"
    assert format_auth_state("2026-06-10T10:00:00+00:00", now=now) == "Valid 10d"
    assert format_auth_state("2026-06-10T12:00:00+00:00", now=now) == "Valid 10d 2h"
    assert format_auth_state("2026-05-31T12:00:00+00:00", now=now) == "Expiring 2h"
    assert format_auth_state("2026-05-31T10:05:00+00:00", now=now) == "Expiring 5m"
    assert format_auth_state("2026-05-31T07:00:00+00:00", now=now) == "Expired 3h"
    assert format_auth_state("2026-05-29T10:00:00+00:00", now=now) == "Expired 2d"


def test_format_quota_display_hides_free_and_unknown_plans() -> None:
    assert format_quota_display(80, "free") == "80%"
    assert format_quota_display(80, "unknown") == "80%"
    assert format_quota_display(None, None) == "unknown"
    assert format_quota_display(90, "go") == "90% (go)"
    assert format_quota_display(100, "pro") == "100% (pro)"
