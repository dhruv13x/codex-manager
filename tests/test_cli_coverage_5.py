from __future__ import annotations

import pytest

from codex_manager.cli import handle_doctor, handle_sync


def test_handle_doctor_exit(mocker):
    class Args:
        source_dir = "a"
        backup_dir = "b"
    args = Args()

    mocker.patch("codex_manager.cli.run_doctor", side_effect=SystemExit(2))

    with pytest.raises(SystemExit) as excinfo:
        handle_doctor(args)
    assert excinfo.value.code == 2

def test_handle_sync_pull(mocker):
    class Args:
        backup_dir = "b"
        direction = "pull"
        bucket_name = "buck"
        endpoint_url = "e"
        access_key = "a"
        secret_key = "s"
        dry_run = True
    args = Args()

    mock_pull = mocker.patch("codex_manager.cli.pull_backup")
    handle_sync(args)
    mock_pull.assert_called_once()
