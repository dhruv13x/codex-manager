import pytest
import json
from pathlib import Path
from types import SimpleNamespace
from codex_manager.remove import perform_remove
import codex_manager.registry

def test_perform_remove_local(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    email = "test@example.com"
    
    # Create dummy files
    f1 = backup_dir / f"{email}-2026-01-01-codex.tar.gz"
    f2 = backup_dir / f"{email}-2026-01-01-codex.metadata.json"
    f3 = backup_dir / "other@example.com-2026-01-01-codex.tar.gz"
    f1.write_text("data")
    f2.write_text("data")
    f3.write_text("data")
    
    # Setup registry
    registry_path = tmp_path / "cooldown.json"
    monkeypatch.setattr(codex_manager.registry, "COOLDOWN_REGISTRY_PATH", registry_path)
    codex_manager.registry.save_registry({email: {"status": "ready"}, "other@example.com": {"status": "ready"}})
    
    args = SimpleNamespace(
        email=email,
        backup_dir=str(backup_dir),
        dry_run=False,
        cloud=False,
        yes=True
    )
    
    results = perform_remove(args)
    
    assert len(results["local_files_removed"]) == 2
    assert not f1.exists()
    assert not f2.exists()
    assert f3.exists()
    assert results["local_registry_removed"] is True
    
    registry = codex_manager.registry.load_registry()
    assert email not in registry
    assert "other@example.com" in registry

def test_perform_remove_dry_run(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    email = "test@example.com"
    f1 = backup_dir / f"{email}-codex.tar.gz"
    f1.write_text("data")
    
    registry_path = tmp_path / "cooldown.json"
    monkeypatch.setattr(codex_manager.registry, "COOLDOWN_REGISTRY_PATH", registry_path)
    codex_manager.registry.save_registry({email: {"status": "ready"}})
    
    args = SimpleNamespace(
        email=email,
        backup_dir=str(backup_dir),
        dry_run=True,
        cloud=False,
        yes=True
    )
    
    results = perform_remove(args)
    assert len(results["local_files_removed"]) == 1
    assert f1.exists()
    assert results["local_registry_removed"] is True
    assert email in codex_manager.registry.load_registry()


def test_perform_remove_cloud_overwrites_registry_without_deleted_email(tmp_path, monkeypatch, mocker):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    email = "test@example.com"

    registry_path = tmp_path / "cooldown.json"
    monkeypatch.setattr(codex_manager.registry, "COOLDOWN_REGISTRY_PATH", registry_path)
    codex_manager.registry.save_registry(
        {
            email: {"status": "ready", "updated_at": "2026-01-01T00:00:00+00:00"},
            "other@example.com": {"status": "ready", "updated_at": "2026-01-02T00:00:00+00:00"},
        }
    )

    mock_cp = mocker.Mock()
    mock_file = mocker.Mock()
    mock_file.name = f"{email}-2026-01-01-codex.metadata.json"
    mock_cp.list_files.return_value = [mock_file]

    mocker.patch("codex_manager.cloud.get_cloud_provider", return_value=mock_cp)
    mock_sync = mocker.patch("codex_manager.remove.sync_registry_with_cloud")
    mock_upload = mocker.patch("codex_manager.remove.upload_registry_to_cloud")

    args = SimpleNamespace(
        email=email,
        backup_dir=str(backup_dir),
        dry_run=False,
        cloud=True,
        yes=True,
    )

    results = perform_remove(args)

    assert results["local_registry_removed"] is True
    assert results["cloud_registry_removed"] is True
    mock_sync.assert_called_once_with(mock_cp)
    mock_cp.delete_file.assert_called_once_with(f"{email}-2026-01-01-codex.metadata.json")
    mock_upload.assert_called_once_with(mock_cp)
