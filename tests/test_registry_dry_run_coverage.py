from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from codex_manager.registry import sync_registry_with_cloud, update_registry_entry

def test_sync_registry_with_cloud_dry_run(mocker, capsys) -> None:
    mock_cp = MagicMock()
    mock_file = MagicMock()
    mock_file.name = "cooldown.json"
    mock_cp.list_files.return_value = [mock_file]

    mocker.patch("codex_manager.registry.load_registry", return_value={"test@test.com": {}})
    mock_save = mocker.patch("codex_manager.registry.save_registry")

    def mock_download(remote, local):
        local.write_text(json.dumps({"remote@test.com": {}}), encoding="utf-8")
    mock_cp.download_file = mock_download

    sync_registry_with_cloud(mock_cp, dry_run=True)

    captured = capsys.readouterr()
    assert "Would merge cloud registry with local registry" in captured.out
    assert "Would upload registry to cloud" in captured.out
    mock_save.assert_not_called()

def test_update_registry_entry_dry_run(mocker, capsys) -> None:
    mocker.patch("codex_manager.registry.load_registry", return_value={"test@example.com": {}})
    mock_save = mocker.patch("codex_manager.registry.save_registry")

    now = datetime.now()

    update_registry_entry(
        email="test@example.com",
        reset_at=now,
        is_expired=True,
        quota_text="testing",
        quota_percent_left=10,
        session_start_at=now,
        dry_run=True,
    )

    captured = capsys.readouterr()
    assert "Would update registry entry for test@example.com" in captured.out
    mock_save.assert_not_called()
