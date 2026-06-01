from __future__ import annotations

import time
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
    # Under Separate Stores, 2 manual runs create 2 auth backups + 2 session backups = 4 entries
    assert len(entries) == 4

    filtered = list_backups(tmp_path / "backups", email="a@example.com")
    # Both auth backup and session backup belong to a@example.com
    assert len(filtered) == 2
    assert filtered[0].email == "a@example.com"


def test_list_backups_latest_per_email(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    status_1 = tmp_path / "status-1.txt"
    status_1.write_text(
        "Email : test@example.com\nQuota : [####] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )
    # simulate an older backup (resets on 19 Apr = session start 12 Apr)
    status_2 = tmp_path / "status-2.txt"
    status_2.write_text(
        "Email : test@example.com\nQuota : [####] 0% left (resets 10:02 on 19 Apr)\n",
        encoding="utf-8",
    )

    perform_backup(make_backup_args(tmp_path, source_dir, status_2))
    time.sleep(0.1) # ensure creation time is different
    perform_backup(make_backup_args(tmp_path, source_dir, status_1))

    entries = list_backups(tmp_path / "backups")
    # 2 manual runs create 1 overwritten in-place auth backup + 2 session backups = 3 entries
    assert len(entries) == 3

    filtered = list_backups(tmp_path / "backups", latest_per_email=True)
    # 1 latest entry for test@example.com
    assert len(filtered) == 1


def test_list_backups_ready(tmp_path: Path, mocker) -> None:
    from datetime import datetime, timezone

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    status = tmp_path / "status.txt"
    status.write_text(
        "Email : ready@example.com\nQuota : [####] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    perform_backup(make_backup_args(tmp_path, source_dir, status))

    # Mock datetime so 'now' is AFTER 26 Apr 2026
    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)

    import codex_manager.list_backups
    codex_manager.list_backups.datetime = MockDatetime

    filtered = list_backups(tmp_path / "backups", email="ready@example.com", ready=True)
    # Both auth and session are ready
    assert len(filtered) == 2

    # Mock datetime so 'now' is BEFORE 26 Apr 2026
    class MockDatetimeBefore(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)

    codex_manager.list_backups.datetime = MockDatetimeBefore

    filtered_empty = list_backups(tmp_path / "backups", email="ready@example.com", ready=True)
    assert len(filtered_empty) == 0


def test_list_backups_sort_by(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    status_1 = tmp_path / "status-1.txt"
    status_1.write_text(
        "Email : z@example.com\nQuota : [####] 0% left (resets 10:02 on 28 Apr)\n",
        encoding="utf-8",
    )
    status_2 = tmp_path / "status-2.txt"
    status_2.write_text(
        "Email : a@example.com\nQuota : [####] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    perform_backup(make_backup_args(tmp_path, source_dir, status_1))
    perform_backup(make_backup_args(tmp_path, source_dir, status_2))

    entries = list_backups(tmp_path / "backups", email="z@example.com")
    # Both auth and session backups are found for z@example.com
    assert len(entries) == 2
