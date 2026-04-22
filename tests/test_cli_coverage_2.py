from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from codex_manager.cli import list_entries_from_args, _read_status_command_input
from codex_manager.status import TokenExpiredError

def test_list_entries_from_args_cloud_disabled_force_latest(mocker, tmp_path):
    class Args:
        command = "cooldown"
        backup_dir = str(tmp_path)
        cloud = False
        email = None
        ready = False
        sort = "created_at"
    args = Args()

    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=None)
    # Should not exit because cloud is false
    assert list_entries_from_args(args) == []

def test_read_status_command_input_sys_stdin(mocker):
    class Args:
        input_file = None
        status_command = None
    args = Args()

    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = False
    mock_stdin.read.return_value = "stdin"
    mocker.patch("codex_manager.cli.sys.stdin", mock_stdin)

    assert _read_status_command_input(args) == "stdin"
