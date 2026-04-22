from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codex_manager.cli import _ensure_cloud_archive, list_entries_from_args


def test_list_entries_force_latest_no_cloud_but_force(mocker, tmp_path):
    class Args:
        command = "cooldown" # implies force_latest=True
        backup_dir = str(tmp_path)
        cloud = False
        email = None
        ready = False
        sort = "created_at"

    args = Args()

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)
    mocker.patch("codex_manager.cli.sync_registry_with_cloud")
    mocker.patch("codex_manager.cli.list_cloud_backups", return_value=[])

    entries = list_entries_from_args(args)
    assert entries == []

def test_ensure_cloud_archive_use_no_entries(mocker):
    class Args:
        cloud = True
        from_archive = None
        email = None
        command = "use"
    args = Args()

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)
    mocker.patch("codex_manager.cli.list_cloud_backups", return_value=[])

    with pytest.raises(SystemExit):
        _ensure_cloud_archive(args)
