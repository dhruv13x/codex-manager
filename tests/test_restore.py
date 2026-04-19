from __future__ import annotations

import json
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
        tmux_session_name="codexmgr_capture",
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
    archive_path, _, _ = perform_backup(make_backup_args(tmp_path, source_dir, status_file))
    return archive_path


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
    (dest_dir / "auth.json").write_text("old", encoding="utf-8")

    _, dest, metadata, previous = perform_restore(
        make_restore_args(tmp_path, archive_path, dest_dir)
    )

    assert dest == dest_dir
    assert metadata["email"] == "letsmaildhruv@gmail.com"
    assert previous is not None
    assert dest_dir.exists()
    assert (dest_dir / "auth.json").read_text(encoding="utf-8") == '{"token":"x"}'
    assert (dest_dir / "history.jsonl").exists()
    assert not list(dest_dir.glob("*.metadata.json"))


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
