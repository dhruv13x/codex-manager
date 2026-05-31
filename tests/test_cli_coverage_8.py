from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from codex_manager.cli import (
    handle_list_backups,
    handle_prune,
    handle_purge,
    handle_remove,
    list_entries_from_args,
    main,
)
from codex_manager.list_backups import BackupEntry


def test_list_entries_from_args_seen_emails(mocker, tmp_path):
    class Args:
        command = "list"
        backup_dir = str(tmp_path)
        latest_per_email = True
        cloud = False
        email = None
        ready = False
        sort = "created_at"

    args = Args()

    now = datetime.now()
    entry1 = BackupEntry("test@test.com", now, now, now, "local", Path(""), "q", 0, False)
    entry2 = BackupEntry("test@test.com", now, now, now, "local", Path(""), "q", 0, False)

    mocker.patch("codex_manager.cli.list_backups", return_value=[entry1, entry2])
    tmp_path.joinpath("fake").write_text("fake")

    entries = list_entries_from_args(args)
    assert len(entries) == 1

def test_handle_list_backups_json(mocker, capsys):
    class Args:
        command = "list"
        backup_dir = "b"
        latest_per_email = False
        cloud = False
        email = None
        ready = False
        sort = "created_at"
        json = True
    args = Args()

    now = datetime.now()
    entry = BackupEntry("test@test.com", now, now, now, "local", Path(""), "q", 0, False)
    mocker.patch("codex_manager.cli.list_entries_from_args", return_value=[entry])

    handle_list_backups(args)
    captured = capsys.readouterr()
    assert "test@test.com" in captured.out

def test_handle_prune(mocker, capsys):
    class Args:
        source_dir = "a"
        dry_run = True
    args = Args()

    mocker.patch("codex_manager.cli.perform_prune", return_value=MagicMock())
    mocker.patch("codex_manager.cli.prune_result_to_text", return_value="prune output")

    handle_prune(args)
    captured = capsys.readouterr()
    assert "prune output" in captured.out

def test_handle_prune_default_dry_run(mocker, capsys):
    class Args:
        source_dir = "a"
        dry_run = False
    args = Args()

    mocker.patch("codex_manager.cli.perform_prune", return_value=MagicMock())
    mocker.patch("codex_manager.cli.prune_result_to_text", return_value="prune output")

    handle_prune(args)
    assert args.dry_run is True  # defaults to dry_run without --yes

def test_handle_prune_with_yes(mocker, capsys):
    class Args:
        source_dir = "a"
        dry_run = False
        yes = True
    args = Args()

    mocker.patch("codex_manager.cli.perform_prune", return_value=MagicMock())
    mocker.patch("codex_manager.cli.prune_result_to_text", return_value="prune output")

    handle_prune(args)
    assert args.dry_run is False  # runs actual delete when yes=True

def test_main_no_handler(mocker):
    # Just to provide branch coverage where handler is not found
    mocker.patch("codex_manager.config.load_config")
    mock_parser = MagicMock()
    mocker.patch("codex_manager.cli.get_parser", return_value=mock_parser)
    mock_args = MagicMock()
    mock_args.command = "unknown"
    mock_parser.parse_args.return_value = mock_args

    main()
    mock_parser.print_help.assert_called_once()

def test_handle_purge_default_dry_run(mocker):
    class Args:
        source_dir = "a"
        dry_run = False
    args = Args()

    mocker.patch("codex_manager.cli.perform_purge", return_value=True)
    mocker.patch("codex_manager.cli.purge_result_to_text", return_value="purge output")

    handle_purge(args)
    assert args.dry_run is True

def test_handle_purge_with_yes(mocker):
    class Args:
        source_dir = "a"
        dry_run = False
        yes = True
    args = Args()

    mocker.patch("codex_manager.cli.perform_purge", return_value=True)
    mocker.patch("codex_manager.cli.purge_result_to_text", return_value="purge output")

    handle_purge(args)
    assert args.dry_run is False

def test_handle_remove_default_dry_run(mocker):
    class Args:
        source_dir = "a"
        dry_run = False
        email = "test@test.com"
    args = Args()

    mocker.patch("codex_manager.cli._apply_remove_target")
    mocker.patch("codex_manager.cli.perform_remove", return_value={})
    mocker.patch("codex_manager.cli.remove_result_to_text", return_value="remove output")

    handle_remove(args)
    assert args.dry_run is True

def test_handle_remove_with_yes(mocker):
    class Args:
        source_dir = "a"
        dry_run = False
        email = "test@test.com"
        yes = True
    args = Args()

    mocker.patch("codex_manager.cli._apply_remove_target")
    mocker.patch("codex_manager.cli.perform_remove", return_value={})
    mocker.patch("codex_manager.cli.remove_result_to_text", return_value="remove output")

    handle_remove(args)
    assert args.dry_run is False
