import sys
from pathlib import Path
from types import SimpleNamespace
from codex_manager.cli import handle_backup
import pytest

def test_handle_backup_file_exists_clean_error(tmp_path, capsys, mocker):
    # Setup
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    archive_name = "2026-01-01-test@example.com-codex.tar.gz"
    (backup_dir / archive_name).write_text("existing")
    
    args = SimpleNamespace(
        command="backup",
        backup_dir=str(backup_dir),
        force=False,
        cloud=False,
        dry_run=False
    )
    
    # Mock perform_backup to raise the error like it does in real life
    mocker.patch("codex_manager.cli.perform_backup", side_effect=FileExistsError(f"Archive already exists: {archive_name}. Use --force to overwrite."))
    
    with pytest.raises(SystemExit) as exc:
        handle_backup(args)
    
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Stop:" in captured.out
    assert "--force" in captured.out
    assert "weekly reset time" in captured.out

if __name__ == "__main__":
    # Just a simple run to see it visually if needed
    pass
