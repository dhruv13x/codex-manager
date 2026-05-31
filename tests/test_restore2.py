from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from codex_manager.restore import (
    identify_auth_email,
    latest_backup_archive,
    load_metadata_for_archive,
    move_existing_target,
    resolve_archive_path,
    restore_result_to_text,
    validate_archive_contents,
)


def test_latest_backup_archive_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        latest_backup_archive(tmp_path / "does_not_exist")

def test_latest_backup_archive_empty(tmp_path):
    d = tmp_path / "b"
    d.mkdir()
    with pytest.raises(FileNotFoundError):
        latest_backup_archive(d)

def test_resolve_archive_path_from_archive(tmp_path):
    f = tmp_path / "a-codex.tar.gz"
    f.write_text("x")
    args = SimpleNamespace(from_archive=str(f))
    assert resolve_archive_path(args) == f.resolve()

def test_resolve_archive_path_email(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    f = d / "foo-latest-codex.tar.gz"
    f.write_text("x")
    args = SimpleNamespace(from_archive=None, email="foo", backup_dir=str(d))
    assert resolve_archive_path(args) == f.resolve()

def test_latest_backup_archive_with_email(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    f1 = d / "2026-04-19-100200-foo@example.com-codex.tar.gz"
    f2 = d / "2026-04-19-110200-foo@example.com-codex.tar.gz"
    f3 = d / "2026-04-19-120200-bar@example.com-codex.tar.gz"
    f1.write_text("x")
    f2.write_text("x")
    f3.write_text("x")
    
    # Should pick latest for foo
    assert latest_backup_archive(d, email="foo@example.com") == f2.resolve()
    # Should pick latest for bar
    assert latest_backup_archive(d, email="bar@example.com") == f3.resolve()
    # Should fail for missing email
    with pytest.raises(FileNotFoundError, match="No Codex backup archives found for email baz"):
        latest_backup_archive(d, email="baz")

def test_resolve_archive_path_email_fallback(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    f = d / "2026-04-19-100200-foo@example.com-codex.tar.gz"
    f.write_text("x")
    
    # Symlink is missing, should fall back to finding latest archive
    args = SimpleNamespace(from_archive=None, email="foo@example.com", backup_dir=str(d))
    assert resolve_archive_path(args) == f.resolve()

def test_resolve_archive_path_missing(tmp_path):
    args = SimpleNamespace(from_archive=str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError):
        resolve_archive_path(args)

def test_resolve_archive_path_safety_backup(tmp_path, monkeypatch):
    safety_dir = tmp_path / "safety_backups"
    safety_dir.mkdir()
    f = safety_dir / ".codex.test@example.com.bak-12345.tar.gz"
    f.write_text("x")
    
    monkeypatch.setattr("codex_manager.restore.CODEX_MANAGER_HOME", tmp_path)
    args = SimpleNamespace(from_archive=".codex.test@example.com.bak-12345.tar.gz")
    assert resolve_archive_path(args) == f.resolve()

def test_load_metadata_for_safety_backup():
    p1 = Path("/tmp/.codex.test@example.com.bak-12345.tar.gz")
    m1 = load_metadata_for_archive(p1)
    assert m1["email"] == "test@example.com"
    
    p2 = Path("/tmp/auth.json.other@example.com.bak-123.tar.gz")
    m2 = load_metadata_for_archive(p2)
    assert m2["email"] == "other@example.com"
    
    p3 = Path("/tmp/something.bak-123.tar.gz")
    m3 = load_metadata_for_archive(p3)
    assert m3["email"] == "unknown"


@patch("codex_manager.restore.tarfile.open")
def test_load_metadata_for_archive_missing(mock_tar_open, tmp_path):
    f = tmp_path / "a-codex.tar.gz"
    f.write_text("x")

    mock_tar = MagicMock()
    mock_tar.getmember.side_effect = KeyError("not found")
    mock_tar_open.return_value.__enter__.return_value = mock_tar

    with pytest.raises(FileNotFoundError):
        load_metadata_for_archive(f)

@patch("codex_manager.restore.tarfile.open")
def test_validate_archive_contents_fail(mock_tar_open, tmp_path):
    f = tmp_path / "a-codex.tar.gz"
    f.write_text("x")

    mock_tar = MagicMock()
    mock_tar.getnames.return_value = ["other"]
    mock_tar_open.return_value.__enter__.return_value = mock_tar

    with pytest.raises(ValueError):
        validate_archive_contents(f)

def test_move_existing_target_none(tmp_path):
    assert move_existing_target(tmp_path / "missing") is None


def test_move_existing_target_no_auth(tmp_path):
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    (dest_dir / "goals_1.sqlite").write_text("db")
    
    assert move_existing_target(dest_dir) is None
    assert not dest_dir.exists()


def test_move_existing_target_with_auth(tmp_path, monkeypatch):
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    (dest_dir / "auth.json").write_text("auth")
    
    # Patch CODEX_MANAGER_HOME
    monkeypatch.setattr("codex_manager.restore.CODEX_MANAGER_HOME", tmp_path)
    
    backup_path = move_existing_target(dest_dir)
    assert backup_path is not None
    assert backup_path.exists()
    assert backup_path.name.endswith(".tar.gz")
    
    import tarfile
    with tarfile.open(backup_path, "r:gz") as tar:
        names = tar.getnames()
        assert "auth.json" in names
    assert not dest_dir.exists()


def test_move_existing_target_with_auth_and_email(tmp_path, monkeypatch):
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    (dest_dir / "auth.json").write_text('{"email":"vurhd1999@gmail.com"}', encoding="utf-8")
    
    # Patch CODEX_MANAGER_HOME
    monkeypatch.setattr("codex_manager.restore.CODEX_MANAGER_HOME", tmp_path)
    
    backup_path = move_existing_target(dest_dir)
    assert backup_path is not None
    assert backup_path.exists()
    assert "vurhd1999@gmail.com" in backup_path.name
    assert backup_path.name.endswith(".tar.gz")
    
    import tarfile
    with tarfile.open(backup_path, "r:gz") as tar:
        names = tar.getnames()
        assert "auth.json" in names
    assert not dest_dir.exists()


def test_move_existing_target_fallback_active_email(tmp_path, monkeypatch):
    dest_dir = tmp_path / "codex"
    dest_dir.mkdir()
    (dest_dir / "auth.json").write_text("auth")
    
    # Patch CODEX_MANAGER_HOME
    monkeypatch.setattr("codex_manager.restore.CODEX_MANAGER_HOME", tmp_path)
    
    with patch("codex_manager.registry.get_active_account", return_value="active@example.com"):
        backup_path = move_existing_target(dest_dir)
        assert backup_path is not None
        assert backup_path.exists()
        assert "active@example.com" in backup_path.name
        assert backup_path.name.endswith(".tar.gz")
        assert not dest_dir.exists()


def test_identify_auth_email(tmp_path):
    auth_path = tmp_path / "auth.json"
    auth_path.write_text('{"email":"test@example.com"}', encoding="utf-8")
    assert identify_auth_email(auth_path) == "test@example.com"


def test_identify_auth_email_invalid(tmp_path):
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("invalid", encoding="utf-8")
    assert identify_auth_email(auth_path) is None

def test_restore_result_to_text():
    res = restore_result_to_text(Path("a"), Path("b"), {"email": "c", "session_start_at": "d", "reset_at": "e", "quota_text": "f"}, Path("g"), dry_run=True)
    assert "dry-run" in res
    assert "safety_backup" in res
