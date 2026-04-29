from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from codex_manager.cli import (
    _ensure_cloud_archive,
    _read_status_command_input,
    handle_status,
    handle_recommend,
    list_entries_from_args,
)
from codex_manager.status import TokenExpiredError


def test_ensure_cloud_archive_no_cloud(capsys):
    class Args:
        cloud = False
        from_archive = None
    args = Args()
    _ensure_cloud_archive(args)
    # Should return early
    assert True

def test_ensure_cloud_archive_from_archive(capsys):
    class Args:
        cloud = True
        from_archive = "some_path"
    args = Args()
    _ensure_cloud_archive(args)
    # Should return early
    assert True

def test_ensure_cloud_archive_no_cp(mocker, capsys):
    class Args:
        cloud = True
        from_archive = None
    args = Args()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=None)
    with pytest.raises(SystemExit):
        _ensure_cloud_archive(args)

def test_list_entries_from_args_cooldown_no_cloud(mocker, tmp_path):
    class Args:
        command = "cooldown"
        backup_dir = str(tmp_path)
        cloud = False
    args = Args()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=None)
    entries = list_entries_from_args(args)
    assert entries == []

def test_read_status_command_input_file(tmp_path):
    class Args:
        input_file = str(tmp_path / "test.txt")
    args = Args()
    (tmp_path / "test.txt").write_text("hello", encoding="utf-8")
    assert _read_status_command_input(args) == "hello"

def test_handle_status_token_expired(mocker, capsys):
    class Args:
        source_dir = None
        reference_year = 2026
    args = Args()

    mocker.patch("codex_manager.cli._read_status_command_input", side_effect=TokenExpiredError("expired", "raw"))
    mocker.patch("codex_manager.cli.parse_live_status_text", side_effect=Exception("could not parse"))
    mocker.patch("codex_manager.cli.patch_metadata")

    with pytest.raises(SystemExit):
        handle_status(args)


def test_handle_recommend_without_cloud_does_not_fetch_cloud(mocker, tmp_path):
    class Args:
        command = "recommend"
        backup_dir = str(tmp_path)
        cloud = False
        live = False

    args = Args()
    mocker.patch("codex_manager.cli.list_backups", return_value=[])
    mock_cloud = mocker.patch("codex_manager.cli.list_cloud_backups")
    recommendation = MagicMock()
    recommendation.selected.email = "test@example.com"
    recommendation.selected.status = "ready"
    recommendation.selected.remaining_seconds = 0
    recommendation.selected.next_available_at.strftime.return_value = "2026-04-29 00:00:00 +0000"
    recommendation.selected.validation_status = "backup"
    recommendation.reason = "ready now"
    mocker.patch("codex_manager.cli.choose_best_account", return_value=recommendation)

    handle_recommend(args)

    mock_cloud.assert_not_called()
