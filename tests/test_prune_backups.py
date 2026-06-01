from __future__ import annotations

import time
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
        no_auto_prune=True,
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
    # 1 auth backup (test@example.com) + 5 session backups (test@example.com) = 6 entries
    assert len(list_backups(backup_dir)) == 6

    perform_prune_backups(backup_dir, keep=2)
    entries = list_backups(backup_dir)
    # keeps the 1 auth backup + 2 latest session backups = 3 entries
    assert len(entries) == 3
    
    # Filter only session entries to verify
    session_entries = [e for e in entries if "sessions" in str(e.archive_path)]
    assert len(session_entries) == 2
    assert "100500" in session_entries[0].archive_path.name
    assert "100400" in session_entries[1].archive_path.name


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
    # 2 auth backups (a and b) + 3 session backups = 5 entries
    assert len(list_backups(backup_dir)) == 5

    perform_prune_backups(backup_dir, keep=1)

    entries = list_backups(backup_dir)
    # keeps 2 auth backups (a and b) + 2 latest session backups (1 for a, 1 for b) = 4 entries
    assert len(entries) == 4
    
    # Verify the latest session backup for user a has Minute 3 in its name
    session_entries = [e for e in entries if "sessions" in str(e.archive_path)]
    a_sessions = [e for e in session_entries if e.email == "a@example.com"]
    b_sessions = [e for e in session_entries if e.email == "b@example.com"]
    assert len(a_sessions) == 1
    assert len(b_sessions) == 1
    assert "100300" in a_sessions[0].archive_path.name
    assert "100200" in b_sessions[0].archive_path.name


def test_prune_backups_keep_one_per_email_logic(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Create 2 backups for user1
    status1_1 = tmp_path / "status-u1-1.txt"
    status1_1.write_text("Email : u1@example.com\nQuota : [####] 0% left (resets 10:01 on 26 Apr)\n", encoding="utf-8")
    perform_backup(make_backup_args(tmp_path, source_dir, status1_1))
    
    status1_2 = tmp_path / "status-u1-2.txt"
    status1_2.write_text("Email : u1@example.com\nQuota : [####] 0% left (resets 10:02 on 26 Apr)\n", encoding="utf-8")
    perform_backup(make_backup_args(tmp_path, source_dir, status1_2))

    # Create 1 backup for user2
    status2_1 = tmp_path / "status-u2-1.txt"
    status2_1.write_text("Email : u2@example.com\nQuota : [####] 0% left (resets 10:03 on 26 Apr)\n", encoding="utf-8")
    perform_backup(make_backup_args(tmp_path, source_dir, status2_1))

    # 2 auth backups + 3 session backups = 5 entries
    assert len(list_backups(backup_dir)) == 5

    # Prune with --keep 1
    perform_prune_backups(backup_dir, keep=1)

    entries = list_backups(backup_dir)
    # 2 auth backups + 2 latest session backups = 4 entries
    assert len(entries) == 4


def test_prune_backups_keep_zero_error(tmp_path: Path, capsys) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    
    perform_prune_backups(backup_dir, keep=0)
    
    captured = capsys.readouterr()
    assert "Error: --keep 0 is not executable" in captured.err
    assert "One copy per email backup will always stay" in captured.err
