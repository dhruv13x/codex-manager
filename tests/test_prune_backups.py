from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codex_manager.backup import perform_backup
from codex_manager.list_backups import list_backups
from codex_manager.prune_backups import perform_prune_backups


def make_backup_args(tmp_path: Path, source_dir: Path, status_file: Path):
    return SimpleNamespace(
        source_dir=str(source_dir),
        backup_dir=str(tmp_path / "backups"),
        status_file=str(status_file),
        status_command=None,
        reference_year=2026,
        codex_command="codex --no-alt-screen",
        tmux_session_name="codex_manager_capture",
        tmux_cols=120,
        tmux_rows=40,
        startup_timeout_seconds=20.0,
        status_timeout_seconds=20.0,
        include_tmp=False,
        dry_run=False,
        force=True,
        auth_only=False,
        prune_first=False,
    )


def test_prune_backups_keep(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    import time
    for i in range(1, 6):
        status = tmp_path / f"status-{i}.txt"
        status.write_text(
            f"Email : test@example.com\nQuota : [####] 0% left (resets 10:0{i} on 26 Apr)\n",
            encoding="utf-8",
        )
        perform_backup(make_backup_args(tmp_path, source_dir, status))
        time.sleep(0.1)

    backup_dir = tmp_path / "backups"
    assert len(list_backups(backup_dir)) == 5

    perform_prune_backups(backup_dir, keep=2)
    entries = list_backups(backup_dir)
    assert len(entries) == 2
    # The remaining backups should be the ones with minute 04 and 05 since they are most recent.
    # Note: list_backups returns newest first by default if sort_by=created_at
    assert "100500" in entries[0].archive_path.name
    assert "100400" in entries[1].archive_path.name


def test_prune_backups_keep_latest_per_email(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    import time

    # User A - old backup
    status = tmp_path / "status-a1.txt"
    status.write_text(
        "Email : a@example.com\nQuota : [####] 0% left (resets 10:01 on 26 Apr)\n",
        encoding="utf-8",
    )
    perform_backup(make_backup_args(tmp_path, source_dir, status))
    time.sleep(0.1)

    # User B - old backup
    status = tmp_path / "status-b1.txt"
    status.write_text(
        "Email : b@example.com\nQuota : [####] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )
    perform_backup(make_backup_args(tmp_path, source_dir, status))
    time.sleep(0.1)

    # User A - new backup
    status = tmp_path / "status-a2.txt"
    status.write_text(
        "Email : a@example.com\nQuota : [####] 0% left (resets 10:03 on 26 Apr)\n",
        encoding="utf-8",
    )
    perform_backup(make_backup_args(tmp_path, source_dir, status))

    backup_dir = tmp_path / "backups"
    assert len(list_backups(backup_dir)) == 3

    perform_prune_backups(backup_dir, keep_latest_per_email=True)

    entries = list_backups(backup_dir)
    assert len(entries) == 2
    emails = {e.email for e in entries}
    assert emails == {"a@example.com", "b@example.com"}

    # User A should have the 10:03 backup
    a_entry = next(e for e in entries if e.email == "a@example.com")
    assert "100300" in a_entry.archive_path.name
