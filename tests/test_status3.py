from datetime import datetime, timezone

from codex_manager.status import parse_live_status_text


def test_parse_live_status_text():
    # test parsing the exact actual format
    text = "Account: a@b.com\nWeekly limit: [░] 10% left (resets 10:00 on 26 Apr)"
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    ls = parse_live_status_text(text, now=now)
    assert ls.email == "a@b.com"
    assert ls.quota_percent_left == 10

def test_parse_live_status_text_no_percent():
    text = "Account: a@b.com\nWeekly limit: (resets 10:00 on 26 Apr)"
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    ls = parse_live_status_text(text, now=now)
    assert ls.email == "a@b.com"
    assert ls.quota_percent_left is None
