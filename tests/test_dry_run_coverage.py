from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from codex_manager.account_status import patch_metadata, sync_current_account_status
from codex_manager.cli import handle_backup, handle_profile, handle_status
from codex_manager.registry import sync_registry_with_cloud, update_registry_entry
from codex_manager.profile import export_profile, import_profile
import pytest

def test_patch_metadata_dry_run(mocker, tmp_path: Path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    email = "test@example.com"
    archive_name = f"2026-04-19-100200-{email}-codex.metadata.json"
    metadata_path = backup_dir / archive_name
    metadata_path.write_text(json.dumps({"email": email}), encoding="utf-8")

    class Args:
        backup_dir: str
    args = Args()
    args.backup_dir = str(backup_dir)

    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    mocker.patch("codex_manager.account_status.update_registry_entry")
    mocker.patch("codex_manager.account_status.sync_registry_with_cloud")
    mocker.patch("codex_manager.account_status.get_cloud_provider", return_value=None)

    patch_metadata(email, reset_at=now, args=args, dry_run=True)

    captured = capsys.readouterr()
    assert "Would update local metadata" in captured.out

def test_patch_metadata_no_existing_dry_run(mocker, tmp_path: Path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    class Args:
        backup_dir: str
    args = Args()
    args.backup_dir = str(backup_dir)

    email = "test@example.com"
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    mocker.patch("codex_manager.account_status.update_registry_entry")
    mocker.patch("codex_manager.account_status.sync_registry_with_cloud")
    mocker.patch("codex_manager.account_status.get_cloud_provider", return_value=None)

    patch_metadata(email, reset_at=now, args=args, dry_run=True)

    captured = capsys.readouterr()
    assert "Would create cooldown-only metadata" in captured.out

def test_sync_current_account_status_bypassed_dry_run(mocker, tmp_path: Path, capsys) -> None:
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    auth_path = dest_dir / "auth.json"
    auth_path.write_text('{"email": "test@example.com"}', encoding="utf-8")

    class Args:
        dest_dir: str
        without_status_check: bool
        dry_run: bool
        command: str
    args = Args()
    args.dest_dir = str(dest_dir)
    args.without_status_check = True
    args.dry_run = True
    args.command = "test"

    mock_patch = mocker.patch("codex_manager.account_status.patch_metadata")

    sync_current_account_status(args)

    mock_patch.assert_called_once()
    assert mock_patch.call_args.kwargs["dry_run"] is True

def test_patch_metadata_cloud_dry_run(mocker, tmp_path: Path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    class Args:
        backup_dir: str
        cloud: bool
    args = Args()
    args.backup_dir = str(backup_dir)
    args.cloud = True

    email = "test@example.com"
    now = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    mocker.patch("codex_manager.account_status.update_registry_entry")
    mocker.patch("codex_manager.account_status.sync_registry_with_cloud")

    mock_cp = MagicMock()
    mock_entry = MagicMock()
    mock_entry.archive_path.name = "fake.tar.gz"
    mocker.patch("codex_manager.account_status.list_cloud_backups", return_value=[mock_entry])
    mocker.patch("codex_manager.account_status.get_cloud_provider", return_value=mock_cp)

    def mock_download_file(remote, local):
        local.write_text(json.dumps({"email": email}), encoding="utf-8")
    mock_cp.download_file = mock_download_file

    patch_metadata(email, reset_at=now, args=args, dry_run=True)

    captured = capsys.readouterr()
    assert "Would upload updated metadata to Cloud" in captured.out

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

def test_handle_backup_cloud_dry_run(mocker, tmp_path: Path, capsys) -> None:
    class Args:
        cloud: bool
        dry_run: bool
    args = Args()
    args.cloud = True
    args.dry_run = True

    archive_path = Path("fake-archive.tar.gz")
    metadata_path = Path("fake-archive.metadata.json")
    metadata = {"email": "test@example.com", "session_start_at": "1", "reset_at": "1", "quota_text": "1"}

    mocker.patch("codex_manager.cli.perform_backup", return_value=(archive_path, metadata_path, metadata))

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)
    mock_sync = mocker.patch("codex_manager.cli.sync_registry_with_cloud")

    handle_backup(args)

    captured = capsys.readouterr()
    assert "Would upload to Cloud: fake-archive.tar.gz" in captured.out
    mock_sync.assert_called_once_with(mock_cp, dry_run=True)

def test_handle_profile_dry_run(mocker, tmp_path: Path, capsys) -> None:
    class Args:
        action: str
        file: str
        dry_run: bool
    args = Args()
    args.action = "export"
    args.file = str(tmp_path / "test.tar.gz")
    args.dry_run = True

    mock_export = mocker.patch("codex_manager.cli.export_profile")

    handle_profile(args)

    mock_export.assert_called_once()
    assert mock_export.call_args.kwargs["dry_run"] is True

def test_handle_status_dry_run(mocker, capsys) -> None:
    class Args:
        dry_run: bool
        reference_year: int
        source_dir: str | None
        input_file: str | None
        status_command: str | None
        tmux_session_name: str | None
        codex_command: str | None
        tmux_cols: int
        tmux_rows: int
        startup_timeout_seconds: int
        status_timeout_seconds: int

    args = Args()
    args.dry_run = True
    args.reference_year = 2026
    args.source_dir = None
    args.input_file = None
    args.status_command = None
    args.tmux_session_name = None
    args.codex_command = None
    args.tmux_cols = 120
    args.tmux_rows = 40
    args.startup_timeout_seconds = 20
    args.status_timeout_seconds = 20

    mocker.patch("codex_manager.cli._read_status_command_input", return_value="Email : letsmaildhruv@gmail.com\nQuota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:02 on 26 Apr)\n")
    mock_patch = mocker.patch("codex_manager.cli.patch_metadata")

    handle_status(args)

    mock_patch.assert_called_once()
    assert mock_patch.call_args.kwargs["dry_run"] is True

def test_export_profile_dry_run(mocker, tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "test.json").write_text("{}", encoding="utf-8")

    mocker.patch("codex_manager.profile.CODEX_MANAGER_HOME", home)

    out_file = tmp_path / "export.tar.gz"
    export_profile(out_file, dry_run=True)

    assert not out_file.exists()
    captured = capsys.readouterr()
    assert "Would export profile" in captured.out


def test_import_profile_dry_run(mocker, tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "old.json").write_text("{}", encoding="utf-8")

    mocker.patch("codex_manager.profile.CODEX_MANAGER_HOME", home)

    archive_path = tmp_path / "test.tar.gz"
    archive_path.write_text("")

    import_profile(archive_path, dry_run=True)

    assert not (tmp_path / "home.bak").exists()
    captured = capsys.readouterr()
    assert "Would import profile" in captured.out
    assert "Would backup existing profile" in captured.out
