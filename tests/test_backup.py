from __future__ import annotations

import json
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from codex_manager.backup import perform_backup


def make_args(tmp_path: Path, source_dir: Path, status_file: Path, *, dry_run: bool = False):
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
        dry_run=dry_run,
        force=False,
        auth_only=False,
        prune_first=False,
        without_status_check=False,
    )


def test_backup_dry_run_uses_live_status_name(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")
    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : letsmaildhruv@gmail.com\n"
        "Quota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    archive_path, metadata_path, metadata = perform_backup(
        make_args(tmp_path, source_dir, status_file, dry_run=True)
    )

    assert archive_path.name == "backup-2026-04-19-100200-codex.tar.gz"
    assert metadata_path.name == "backup-2026-04-19-100200-codex.metadata.json"
    assert metadata["email"] == "letsmaildhruv@gmail.com"


def test_backup_creates_archive_and_metadata(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")
    (source_dir / "history.jsonl").write_text("line\n", encoding="utf-8")
    (source_dir / "tmp").mkdir()
    (source_dir / "tmp" / "skip.txt").write_text("skip\n", encoding="utf-8")
    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : letsmaildhruv@gmail.com\n"
        "Quota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    archive_path, metadata_path, metadata = perform_backup(
        make_args(tmp_path, source_dir, status_file, dry_run=False)
    )

    assert archive_path.exists()
    assert metadata_path.exists()
    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert loaded["email"] == "letsmaildhruv@gmail.com"

    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert "auth.json" not in names
    assert "history.jsonl" in names
    assert "tmp/skip.txt" not in names
    assert "backup-2026-04-19-100200-codex.metadata.json" in names


def test_backup_auth_only(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")
    (source_dir / "config.toml").write_text("", encoding="utf-8")
    (source_dir / "installation_id").write_text("id", encoding="utf-8")
    (source_dir / "version.json").write_text("{}", encoding="utf-8")
    rules_dir = source_dir / "rules"
    rules_dir.mkdir()
    (rules_dir / "default.rules").write_text("rules content", encoding="utf-8")
    (source_dir / "history.jsonl").write_text("line\n", encoding="utf-8")

    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : test@gmail.com\n"
        "Quota : [░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    args = make_args(tmp_path, source_dir, status_file)
    args.auth_only = True
    archive_path, metadata_path, metadata = perform_backup(args)

    assert metadata["backup_mode"] == "auth-only"
    assert archive_path.name == "latest.tar.gz"
    assert archive_path.parent.name == "test@gmail.com"
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert "auth.json" in names
    assert "config.toml" in names
    assert "installation_id" in names
    assert "version.json" in names
    assert "rules" in names
    assert "rules/default.rules" in names
    assert "history.jsonl" not in names


def test_manual_backup_separates_auth_and_session(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")
    (source_dir / "config.toml").write_text("", encoding="utf-8")
    (source_dir / "installation_id").write_text("id", encoding="utf-8")
    (source_dir / "version.json").write_text("{}", encoding="utf-8")
    rules_dir = source_dir / "rules"
    rules_dir.mkdir()
    (rules_dir / "default.rules").write_text("rules content", encoding="utf-8")
    (source_dir / "history.jsonl").write_text("line\n", encoding="utf-8")
    (source_dir / "state_db.sqlite").write_text("sqlite", encoding="utf-8")

    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : test@gmail.com\n"
        "Quota : [░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    args = make_args(tmp_path, source_dir, status_file)
    args.auth_only = False
    
    # perform_backup for manual backup creates both and returns the session-only archive path
    session_archive_path, session_metadata_path, _ = perform_backup(args)
    auth_archive_path = tmp_path / "backups" / "auth" / "test@gmail.com" / "latest.tar.gz"

    assert session_archive_path.exists()
    assert auth_archive_path.exists()

    # 1. Assert Auth Backup contains only the identity/auth files and directories
    with tarfile.open(auth_archive_path, "r:gz") as tar:
        auth_names = tar.getnames()
    assert "auth.json" in auth_names
    assert "config.toml" in auth_names
    assert "installation_id" in auth_names
    assert "version.json" in auth_names
    assert "rules" in auth_names
    assert "rules/default.rules" in auth_names
    assert "history.jsonl" not in auth_names
    assert "state_db.sqlite" not in auth_names

    # 2. Assert Session Backup contains only the session/database files and excludes the auth/identity files
    with tarfile.open(session_archive_path, "r:gz") as tar:
        session_names = tar.getnames()
    assert "auth.json" not in session_names
    assert "config.toml" not in session_names
    assert "installation_id" not in session_names
    assert "version.json" not in session_names
    assert "rules" not in session_names
    assert "rules/default.rules" not in session_names
    assert "history.jsonl" in session_names
    assert "state_db.sqlite" in session_names


def test_backup_prune_first(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")
    (source_dir / "models_cache.json").write_text("{}", encoding="utf-8")

    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : test@gmail.com\n"
        "Quota : [░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    args = make_args(tmp_path, source_dir, status_file)
    args.prune_first = True
    archive_path, metadata_path, metadata = perform_backup(args)

    assert metadata["pruned_before_backup"] is True
    # Verify prune was run - cache file should be deleted from source
    assert not (source_dir / "models_cache.json").exists()

    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert "auth.json" not in names
    assert "models_cache.json" not in names


def test_backup_without_status_check_uses_estimated_reset_name(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text(
        json.dumps({"email": "test@example.com"}),
        encoding="utf-8",
    )
    status_file = tmp_path / "status.txt"
    status_file.write_text("", encoding="utf-8")

    args = make_args(tmp_path, source_dir, status_file, dry_run=True)
    args.without_status_check = True

    fixed_now = datetime(2026, 4, 21, 11, 18, 38, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    with patch("codex_manager.backup.datetime") as mock_datetime:
        mock_datetime.now.return_value.astimezone.return_value = fixed_now
        archive_path, metadata_path, metadata = perform_backup(args)

    assert archive_path.name == "backup-2026-04-21-111838-codex.tar.gz"
    assert metadata_path.name == "backup-2026-04-21-111838-codex.metadata.json"
    assert metadata["session_start_at"] == fixed_now.isoformat(timespec="seconds")
    assert metadata["reset_at"] == (fixed_now + timedelta(days=7)).isoformat(timespec="seconds")


def test_backup_auto_prunes_older_backups(tmp_path: Path) -> None:
    # Under the Split Stores architecture, auth backups are overwritten in-place in auth/<email>/latest.tar.gz.
    # We verify that taking another auth backup successfully overwrites the existing in-place file.
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    auth_subfolder = backup_dir / "auth" / "letsmaildhruv@gmail.com"
    auth_subfolder.mkdir(parents=True, exist_ok=True)
    old_archive = auth_subfolder / "latest.tar.gz"
    old_metadata = auth_subfolder / "latest.metadata.json"
    old_archive.write_text("dummy archive content", encoding="utf-8")
    old_metadata.write_text("dummy metadata content", encoding="utf-8")

    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : letsmaildhruv@gmail.com\n"
        "Quota : [░░░░░░░░░░░░░░░░░░░░] 0% left (resets 10:05 on 26 Apr)\n",
        encoding="utf-8",
    )

    args = make_args(tmp_path, source_dir, status_file, dry_run=False)
    args.auth_only = True
    
    assert old_archive.exists()
    assert old_metadata.exists()

    archive_path, metadata_path, metadata = perform_backup(args)

    assert archive_path.exists()
    assert metadata_path.exists()
    assert archive_path == old_archive
    assert archive_path.read_bytes() != b"dummy archive content"


def test_backup_no_auth(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "history.jsonl").write_text("line\n", encoding="utf-8")
    (source_dir / "state_db.sqlite").write_text("sqlite", encoding="utf-8")

    status_file = tmp_path / "status.txt"
    status_file.write_text(
        "Email : test@gmail.com\n"
        "Quota : [░] 0% left (resets 10:02 on 26 Apr)\n",
        encoding="utf-8",
    )

    args = make_args(tmp_path, source_dir, status_file)
    args.no_auth = True
    
    session_archive_path, session_metadata_path, metadata = perform_backup(args)
    auth_archive_path = tmp_path / "backups" / "auth" / "test@gmail.com" / "latest.tar.gz"

    assert session_archive_path.exists()
    # Since --no-auth is passed, auth backup is NOT created
    assert not auth_archive_path.exists()
    assert metadata["backup_mode"] == "session-only"

    # Verify session backup contents
    with tarfile.open(session_archive_path, "r:gz") as tar:
        session_names = tar.getnames()
    assert "history.jsonl" in session_names
    assert "state_db.sqlite" in session_names
    assert "auth.json" not in session_names
