from __future__ import annotations

import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

from codex_manager.backup import perform_backup
from codex_manager.restore import perform_restore


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
        force=False,
    )


def make_restore_args(tmp_path: Path, archive_path: Path, dest_dir: Path, *, dry_run: bool = False, force: bool = False):
    return SimpleNamespace(
        from_archive=str(archive_path),
        email=None,
        backup_dir=str(tmp_path / "backups"),
        dest_dir=str(dest_dir),
        dry_run=dry_run,
        force=force,
    )


def create_sample_backup(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text('{"token":"x"}', encoding="utf-8")
    (source_dir / "history.jsonl").write_text("line\n", encoding="utf-8")
    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : letsmaildhruv@gmail.com\n"
        "Quota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )
    # perform_backup returns the session backup path
    perform_backup(make_backup_args(tmp_path, source_dir, status_file))
    # We want to return the auth backup path for credential restores
    return tmp_path / "backups" / "auth" / "letsmaildhruv@gmail.com" / "latest.tar.gz"


def test_restore_dry_run(tmp_path: Path) -> None:
    archive_path = create_sample_backup(tmp_path)
    dest_dir = tmp_path / "restored"

    archive, dest, metadata, previous = perform_restore(
        make_restore_args(tmp_path, archive_path, dest_dir, dry_run=True)
    )

    assert archive == archive_path
    assert dest == dest_dir
    assert metadata["email"] == "letsmaildhruv@gmail.com"
    assert previous is None
    assert not dest_dir.exists()


def test_restore_installs_archive(tmp_path: Path) -> None:
    archive_path = create_sample_backup(tmp_path)
    dest_dir = tmp_path / "restored"
    dest_dir.mkdir()
    (dest_dir / "auth.json").write_text('{"email":"old@example.com"}', encoding="utf-8")

    _, dest, metadata, previous = perform_restore(
        make_restore_args(tmp_path, archive_path, dest_dir)
    )

    assert dest == dest_dir
    assert metadata["email"] == "letsmaildhruv@gmail.com"
    assert previous is not None
    assert dest_dir.exists()
    assert (dest_dir / "auth.json").read_text(encoding="utf-8") == '{"token":"x"}'
    # Under Separate Stores, auth-only restores do NOT overwrite history.jsonl
    assert not (dest_dir / "history.jsonl").exists()


def test_restore_force_replaces_without_backup(tmp_path: Path) -> None:
    archive_path = create_sample_backup(tmp_path)
    dest_dir = tmp_path / "restored"
    dest_dir.mkdir()
    (dest_dir / "auth.json").write_text("old", encoding="utf-8")

    _, _, _, previous = perform_restore(
        make_restore_args(tmp_path, archive_path, dest_dir, force=True)
    )

    assert previous is None
    assert (dest_dir / "auth.json").read_text(encoding="utf-8") == '{"token":"x"}'


def test_restore_auto_saves_active_account(tmp_path: Path) -> None:
    # 1. Create a target backup to restore
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "auth.json").write_text(
        '{"email": "letsmaildhruv@gmail.com"}', encoding="utf-8"
    )
    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : letsmaildhruv@gmail.com\nQuota : [░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )
    perform_backup(make_backup_args(tmp_path, source_dir, status_file))
    archive_path = tmp_path / "backups" / "auth" / "letsmaildhruv@gmail.com" / "latest.tar.gz"

    # 2. Create an active session directory with a DIFFERENT email
    dest_dir = tmp_path / "restored"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "auth.json").write_text(
        '{"email": "active@example.com"}', encoding="utf-8"
    )

    # Make restore arguments
    args = make_restore_args(tmp_path, archive_path, dest_dir)

    # Perform restore
    perform_restore(args)

    # 3. Verify that an auto-saved backup for 'active@example.com' was automatically created in the auth folder!
    backup_dir = tmp_path / "backups"
    assert (backup_dir / "auth" / "active@example.com" / "latest.tar.gz").exists()


def test_restore_auto_saves_preserves_full_mode(tmp_path: Path) -> None:
    # 1. Create a target backup to restore
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "auth.json").write_text(
        '{"email": "letsmaildhruv@gmail.com"}', encoding="utf-8"
    )
    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : letsmaildhruv@gmail.com\nQuota : [░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )
    perform_backup(make_backup_args(tmp_path, source_dir, status_file))
    archive_path = tmp_path / "backups" / "auth" / "letsmaildhruv@gmail.com" / "latest.tar.gz"

    # 2. Create the current active session state in dest_dir
    dest_dir = tmp_path / "restored"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "auth.json").write_text(
        '{"email": "active@example.com"}', encoding="utf-8"
    )
    (dest_dir / "goals_1.sqlite").write_text("new database content", encoding="utf-8")

    # Make restore arguments
    args = make_restore_args(tmp_path, archive_path, dest_dir)

    # Perform restore
    perform_restore(args)

    # Under Split Store, auto-saves are strictly auth-only.
    # Verify the auto-saved archive exists
    backup_dir = tmp_path / "backups"
    auto_backup = backup_dir / "auth" / "active@example.com" / "latest.tar.gz"
    assert auto_backup.exists()
    
    # Assert that database is NOT present inside the tar file of the auto-saved backup!
    with tarfile.open(auto_backup, "r:gz") as tar:
        names = tar.getnames()
    assert "goals_1.sqlite" not in names


def test_restore_active_account_same_email_prevents_self_pruning(tmp_path: Path) -> None:
    # 1. Create a target backup to restore
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "auth.json").write_text(
        '{"email": "letsmaildhruv@gmail.com"}', encoding="utf-8"
    )
    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : letsmaildhruv@gmail.com\nQuota : [░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )
    perform_backup(make_backup_args(tmp_path, source_dir, status_file))
    archive_path = tmp_path / "backups" / "auth" / "letsmaildhruv@gmail.com" / "latest.tar.gz"

    # 2. Create the current active session state in dest_dir with the SAME email
    dest_dir = tmp_path / "restored"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "auth.json").write_text(
        '{"email": "letsmaildhruv@gmail.com"}', encoding="utf-8"
    )

    # Make restore arguments
    args = make_restore_args(tmp_path, archive_path, dest_dir)

    # Perform restore (safety backup is taken and overwrites targets in-place)
    archive_path, dest_dir_out, metadata, auto_backup_path = perform_restore(args)

    assert (dest_dir / "auth.json").exists()
    assert auto_backup_path is not None
    assert auto_backup_path.exists()
    # The file exists because it was overwritten in place
    assert archive_path.exists()
