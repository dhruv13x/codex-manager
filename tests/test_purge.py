import pytest
from pathlib import Path
from types import SimpleNamespace
from codex_manager.purge import perform_purge

def test_perform_purge_dry_run(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "auth.json").write_text("{}")
    
    args = SimpleNamespace(
        source_dir=str(codex_dir),
        dry_run=True,
        yes=False
    )
    
    success = perform_purge(args)
    assert success is True
    assert codex_dir.exists()
    assert (codex_dir / "auth.json").exists()

def test_perform_purge_with_yes(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "auth.json").write_text("{}")
    
    args = SimpleNamespace(
        source_dir=str(codex_dir),
        dry_run=False,
        yes=True
    )
    
    success = perform_purge(args)
    assert success is True
    assert not codex_dir.exists()

def test_perform_purge_no_dir(tmp_path):
    codex_dir = tmp_path / "non_existent"
    
    args = SimpleNamespace(
        source_dir=str(codex_dir),
        dry_run=False,
        yes=True
    )
    
    success = perform_purge(args)
    assert success is False

def test_perform_purge_confirmation_denied(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    
    args = SimpleNamespace(
        source_dir=str(codex_dir),
        dry_run=False,
        yes=False
    )
    
    # Mock Confirm.ask to return False
    from codex_manager.ui import Confirm
    monkeypatch.setattr(Confirm, "ask", lambda prompt: False)
    
    success = perform_purge(args)
    assert success is False
    assert codex_dir.exists()

def test_perform_purge_confirmation_accepted(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    
    args = SimpleNamespace(
        source_dir=str(codex_dir),
        dry_run=False,
        yes=False
    )
    
    # Mock Confirm.ask to return True
    from codex_manager.ui import Confirm
    monkeypatch.setattr(Confirm, "ask", lambda prompt: True)
    
    success = perform_purge(args)
    assert success is True
    assert not codex_dir.exists()
