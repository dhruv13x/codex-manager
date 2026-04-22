from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from codex_manager.cli import build_live_status
from codex_manager.status import LiveStatus
from datetime import datetime, timezone

def test_build_live_status_with_live(mocker):
    class Args:
        live = True
        reference_year = 2026

    args = Args()

    mocker.patch("codex_manager.cli.read_status_text_from_args", return_value="raw")
    now = datetime.now().astimezone()
    mock_status = LiveStatus(
        email="a@a.com",
        reset_at=now,
        session_start_at=now,
        quota_text="test",
        quota_percent_left=0,
        proposed_archive_name="arch",
    )
    mocker.patch("codex_manager.cli.parse_live_status_text", return_value=mock_status)

    res = build_live_status(args)
    assert res is not None
    assert res.email == "a@a.com"
