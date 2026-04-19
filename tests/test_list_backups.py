from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codex_manager.backup import perform_backup
from codex_manager.list_backups import list_backups


def make_backup_args(tmp_path: Path, source_dir: Path, status_file: Path):
    return SimpleNamespace(
        source_dir=str(source_dir),
        backup_dir=str(tmp_path / "backups"),
        status_file=str(status_file),
        status_command=None,
        reference_year=2026,
        codex_command="codex --no-alt-screen",
        tmux_session_name="codexmgr_capture",
        tmux_cols=120,
        tmux_rows=40,
        startup_timeout_seconds=20.0,
        status_timeout_seconds=20.0,
        include_tmp=False,
        dry_run=False,
        force=True,
    )


def test_list_backups_filters_latest_symlink_and_email(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    status_a = tmp_path / "status-a.txt"
    status_a.write_text(
        "Email : a@example.com\n"
        "Quota : [####] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )
    status_b = tmp_path / "status-b.txt"
    status_b.write_text(
        "Email : b@example.com\n"
        "Quota : [####] 0% left (resets 11:02 on 27 Apr)\n",
        encoding="utf-8",
    )

    perform_backup(make_backup_args(tmp_path, source_dir, status_a))
    perform_backup(make_backup_args(tmp_path, source_dir, status_b))

    entries = list_backups(tmp_path / "backups")
    assert len(entries) == 2

    filtered = list_backups(tmp_path / "backups", email="a@example.com")
    assert len(filtered) == 1
    assert filtered[0].email == "a@example.com"
