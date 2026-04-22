from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from codex_manager.cli import _read_status_command_input, handle_status
from codex_manager.status import TokenExpiredError
from pathlib import Path
import json

def test_read_status_command_input_status_command(mocker):
    class Args:
        input_file = None
        status_command = "echo raw"

    args = Args()
    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = True
    mocker.patch("codex_manager.cli.sys.stdin", mock_stdin)

    mocker.patch("codex_manager.cli.read_status_text_from_args", return_value="raw_cmd")

    assert _read_status_command_input(args) == "raw_cmd"


def test_handle_status_token_expired_auth_json_fallback_generic_exception(mocker, tmp_path):
    class Args:
        source_dir = str(tmp_path)
        reference_year = 2026
        dry_run = True
    args = Args()

    # invalid auth.json to trigger exception inside fallback
    (tmp_path / "auth.json").write_text("invalid json")

    mocker.patch("codex_manager.cli._read_status_command_input", side_effect=TokenExpiredError("expired", "raw"))
    mocker.patch("codex_manager.cli.parse_live_status_text", side_effect=Exception("could not parse"))

    with pytest.raises(SystemExit):
        handle_status(args)

def test_handle_status_token_expired_auth_json_fallback_valid(mocker, tmp_path):
    class Args:
        source_dir = str(tmp_path)
        reference_year = 2026
        dry_run = True
    args = Args()

    (tmp_path / "auth.json").write_text(json.dumps({"email": "test@test.com"}))

    mocker.patch("codex_manager.cli._read_status_command_input", side_effect=TokenExpiredError("expired", "raw"))
    mocker.patch("codex_manager.cli.parse_live_status_text", side_effect=Exception("could not parse"))
    # Patch metadata to throw exception inside the inner try/except block
    mocker.patch("codex_manager.cli.patch_metadata", side_effect=Exception("inner patch error"))

    with pytest.raises(SystemExit):
        handle_status(args)
