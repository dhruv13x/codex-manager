from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from codex_manager.cli import (
    handle_list_backups,
    handle_prune,
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
