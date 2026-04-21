from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from codex_manager.status import (
    LiveStatus,
    _extract_email_and_quota,
    _resolve_reset_at,
    capture_tmux_status_text,
    live_status_to_text,
    run_command,
)


def test_extract_email_and_quota_panel():
    text = "Account: a@b.com\nWeekly limit: foo bar\n"
    assert _extract_email_and_quota(text) == ("a@b.com", "foo bar")

def test_extract_email_and_quota_fail():
    text = "random"
    with pytest.raises(ValueError):
        _extract_email_and_quota(text)

def test_extract_email_and_quota_script_fail():
    text = "Email : a@b.com\n"
    with pytest.raises(ValueError):
        _extract_email_and_quota(text)

def test_resolve_reset_at_time_only():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    res = _resolve_reset_at("resets 10:00", now=now, reference_year=2026)
    assert res.hour == 10

def test_resolve_reset_at_fail():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        _resolve_reset_at("no reset", now=now, reference_year=2026)

def test_live_status_to_text():
    ls = LiveStatus("a@b.com", datetime(2026, 4, 1, tzinfo=timezone.utc), datetime(2026, 3, 25, tzinfo=timezone.utc), "foo", 50, "arc")
    res = live_status_to_text(ls)
    from codex_manager.rich_utils import RICH_AVAILABLE
    if RICH_AVAILABLE:
        assert hasattr(res, "columns")
    else:
        assert "a@b.com" in res

@patch("codex_manager.status.run_command")
@patch("codex_manager.status.time.sleep")
def test_capture_tmux_status_text_timeout(mock_sleep, mock_run):
    mock_run.return_value = MagicMock(stdout="not ready")
    with patch("codex_manager.status.time.time", side_effect=[1, 2, 3]):
        with pytest.raises(RuntimeError):
            capture_tmux_status_text(startup_timeout_seconds=0.1, status_timeout_seconds=0.1)

@patch("codex_manager.status.run_command")
@patch("codex_manager.status.time.sleep")
def test_capture_tmux_status_text_success(mock_sleep, mock_run):
    def mock_run_side_effect(args, **kwargs):
        if "capture-pane" in args:
            # We need to simulate the prompt '›' appearing, then the status appearing.
            # Let's count how many times capture-pane is called
            if not hasattr(mock_run_side_effect, "calls"):
                mock_run_side_effect.calls = 0
            mock_run_side_effect.calls += 1
            if mock_run_side_effect.calls == 1:
                return MagicMock(stdout="codex › ")
            elif mock_run_side_effect.calls == 2:
                return MagicMock(stdout="Account: a@b.com\nWeekly limit: foo")

        return MagicMock()

    mock_run.side_effect = mock_run_side_effect
    res = capture_tmux_status_text(startup_timeout_seconds=1.0, status_timeout_seconds=1.0)
    assert "Account: a@b.com" in res

@patch("codex_manager.status.run_command")
@patch("codex_manager.status.time.sleep")
def test_capture_tmux_status_text_retry_and_timeout(mock_sleep, mock_run):
    def mock_run_side_effect(args, **kwargs):
        if "capture-pane" in args:
            # First phase: '›'
            # Second phase: status timeout
            if not hasattr(mock_run_side_effect, "calls"):
                mock_run_side_effect.calls = 0
            mock_run_side_effect.calls += 1
            if mock_run_side_effect.calls == 1:
                return MagicMock(stdout="codex › ")
            else:
                return MagicMock(stdout="loading...")

        return MagicMock()

    mock_run.side_effect = mock_run_side_effect
    # Fast forward time:
    # start phase 1 -> 1
    # start phase 2 -> 1, time.time() inside loop -> 7, 7, 7
    with patch("codex_manager.status.time.time", side_effect=[1, 1, 7, 8]):
        with pytest.raises(RuntimeError):
            capture_tmux_status_text(startup_timeout_seconds=10.0, status_timeout_seconds=5.0)

@patch("codex_manager.status.subprocess.run")
def test_run_command_fail(mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    with pytest.raises(RuntimeError):
        run_command(["foo"])
