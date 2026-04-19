from __future__ import annotations

from datetime import datetime, timezone, timedelta

from codex_manager.status import parse_live_status_text


def test_parse_live_status_from_helper_output() -> None:
    text = (
        "Email : letsmaildhruv@gmail.com\n"
        "Quota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:02 on 26 Apr)\n"
    )
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    status = parse_live_status_text(text, now=now)

    assert status.email == "letsmaildhruv@gmail.com"
    assert status.reset_at == datetime(2026, 4, 26, 10, 2, tzinfo=now.tzinfo)
    assert status.session_start_at == datetime(2026, 4, 19, 10, 2, tzinfo=now.tzinfo)
    assert status.quota_percent_left == 0
    assert status.proposed_archive_name == "2026-04-19-100200-letsmaildhruv@gmail.com-codex.tar.gz"


def test_parse_live_status_from_raw_panel_output() -> None:
    text = (
        "Account: letsmaildhruv@gmail.com\n"
        "Weekly limit: [########............] 40% left (resets 10:02 on 26 Apr)\n"
    )
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    status = parse_live_status_text(text, now=now)

    assert status.email == "letsmaildhruv@gmail.com"
    assert status.reset_at == datetime(2026, 4, 26, 10, 2, tzinfo=timezone.utc)
    assert status.quota_percent_left == 40
