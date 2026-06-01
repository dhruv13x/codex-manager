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
    res = evaluate_entry(entry)
    assert res.status == "ready"
    assert res.next_available_at.year == 1970

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


def test_dual_auth_state_aging_colors():
    from codex_manager.cooldown import format_dual_auth_state
    from datetime import timedelta
    
    # Let's say now is 2026-05-31 20:00:00
    now = datetime(2026, 5, 31, 20, 0, tzinfo=timezone.utc)
    
    # 1. Access Token: 4 days remaining (elapsed = 10 - 4 = 6 days -> Yellow)
    expires_at = (now + timedelta(days=4)).isoformat()
    last_verified_at = now - timedelta(days=1)
    
    res = format_dual_auth_state(
        expires_at=expires_at,
        last_verified_at=last_verified_at,
        is_expired=False,
        has_refresh_token=True,
        now=now,
        rich_markup=True,
    )
    
    assert "yellow" in res   # Access token is Yellow

    # 3. Access Token: 1 day remaining (elapsed = 9 days -> Red)
    expires_at_2 = (now + timedelta(days=1)).isoformat()
    last_verified_at_2 = now - timedelta(days=26)
    
    res_2 = format_dual_auth_state(
        expires_at=expires_at_2,
        last_verified_at=last_verified_at_2,
        is_expired=False,
        has_refresh_token=True,
        now=now,
        rich_markup=True,
    )
    
    assert "red" in res_2     # Access token is Red


def test_dual_auth_state_single_expired():
    from codex_manager.cooldown import format_dual_auth_state
    
    # 1. Test rich markup with expired refresh token
    res_rich = format_dual_auth_state(
        expires_at=None,
        last_verified_at=datetime.now(),
        is_expired=True,
        has_refresh_token=True,
        rich_markup=True,
    )
    assert res_rich == "[bold red]Expired[/]"

    # 2. Test plain text with expired refresh token
    res_plain = format_dual_auth_state(
        expires_at=None,
        last_verified_at=datetime.now(),
        is_expired=True,
        has_refresh_token=True,
        rich_markup=False,
    )
    assert res_plain == "Expired"

