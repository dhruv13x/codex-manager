from __future__ import annotations

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from codex_manager.cli import handle_cooldown
from codex_manager.cooldown import CooldownStatus

def test_handle_cooldown_filters_expired_accounts_by_default():
    class Args:
        limit = 10
        full = False
        all = False

    args = Args()

    # Create dummy status objects. One active expired, one inactive expired (ready), and one inactive expired (cooldown)
    s1 = CooldownStatus(
        email="active-expired@b.com",
        status="active",
        session_start_at=datetime.now(timezone.utc),
        next_available_at=datetime.now(timezone.utc),
        quota_end_detected_at=datetime.now(timezone.utc),
        validation_status="live",
        proposed_archive_name="archive1",
        remaining_seconds=0,
        is_expired=True,
    )
    s2 = CooldownStatus(
        email="inactive-expired-ready@b.com",
        status="ready",
        session_start_at=datetime.now(timezone.utc),
        next_available_at=datetime.now(timezone.utc),
        quota_end_detected_at=datetime.now(timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive2",
        remaining_seconds=0,
        is_expired=True,
    )
    s3 = CooldownStatus(
        email="inactive-expired-cooldown@b.com",
        status="cooldown",
        session_start_at=datetime.now(timezone.utc),
        next_available_at=datetime.now(timezone.utc),
        quota_end_detected_at=datetime.now(timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive3",
        remaining_seconds=1000,
        is_expired=True,
    )

    with patch("codex_manager.cli.list_entries_from_args", return_value=[]), \
         patch("codex_manager.cli.evaluate_records", return_value=[s1, s2, s3]), \
         patch("codex_manager.cli.print_statuses_table") as mock_print:
        
        handle_cooldown(args)
        
        mock_print.assert_called_once()
        printed_statuses = mock_print.call_args[0][0]
        # Verify that inactive expired accounts are filtered out!
        assert len(printed_statuses) == 1
        assert printed_statuses[0].email == "active-expired@b.com"


def test_handle_cooldown_does_not_filter_expired_accounts_with_full():
    class Args:
        limit = 10
        full = True
        all = False

    args = Args()

    s1 = CooldownStatus(
        email="active-expired@b.com",
        status="active",
        session_start_at=datetime.now(timezone.utc),
        next_available_at=datetime.now(timezone.utc),
        quota_end_detected_at=datetime.now(timezone.utc),
        validation_status="live",
        proposed_archive_name="archive1",
        remaining_seconds=0,
        is_expired=True,
    )
    s2 = CooldownStatus(
        email="inactive-expired-ready@b.com",
        status="ready",
        session_start_at=datetime.now(timezone.utc),
        next_available_at=datetime.now(timezone.utc),
        quota_end_detected_at=datetime.now(timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive2",
        remaining_seconds=0,
        is_expired=True,
    )

    with patch("codex_manager.cli.list_entries_from_args", return_value=[]), \
         patch("codex_manager.cli.evaluate_records", return_value=[s1, s2]), \
         patch("codex_manager.cli.print_statuses_table") as mock_print:
        
        handle_cooldown(args)
        
        mock_print.assert_called_once()
        printed_statuses = mock_print.call_args[0][0]
        # Verify that all statuses are preserved when full is True!
        assert len(printed_statuses) == 2


def test_handle_cooldown_does_not_filter_expired_accounts_with_all():
    class Args:
        limit = 10
        full = False
        all = True

    args = Args()

    s1 = CooldownStatus(
        email="active-expired@b.com",
        status="active",
        session_start_at=datetime.now(timezone.utc),
        next_available_at=datetime.now(timezone.utc),
        quota_end_detected_at=datetime.now(timezone.utc),
        validation_status="live",
        proposed_archive_name="archive1",
        remaining_seconds=0,
        is_expired=True,
    )
    s2 = CooldownStatus(
        email="inactive-expired-ready@b.com",
        status="ready",
        session_start_at=datetime.now(timezone.utc),
        next_available_at=datetime.now(timezone.utc),
        quota_end_detected_at=datetime.now(timezone.utc),
        validation_status="backup",
        proposed_archive_name="archive2",
        remaining_seconds=0,
        is_expired=True,
    )

    with patch("codex_manager.cli.list_entries_from_args", return_value=[]), \
         patch("codex_manager.cli.evaluate_records", return_value=[s1, s2]), \
         patch("codex_manager.cli.print_statuses_table") as mock_print:
        
        handle_cooldown(args)
        
        mock_print.assert_called_once()
        printed_statuses = mock_print.call_args[0][0]
        # Verify that all statuses are preserved when all is True!
        assert len(printed_statuses) == 2
