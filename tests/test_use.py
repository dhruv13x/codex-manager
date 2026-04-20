from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codex_manager.backup import perform_backup
from codex_manager.use_account import perform_use


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
    )


def create_sample_backup(tmp_path: Path) -> None:
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
    perform_backup(make_backup_args(tmp_path, source_dir, status_file))


def test_use_preserve_mode_restores_latest_for_email(tmp_path: Path) -> None:
    create_sample_backup(tmp_path)
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    (dest_dir / "auth.json").write_text("old", encoding="utf-8")
    (dest_dir / "history.jsonl").write_text("runtime", encoding="utf-8")
    (dest_dir / "cache").mkdir()

    args = SimpleNamespace(
        from_archive=None,
        email="letsmaildhruv@gmail.com",
        backup_dir=str(tmp_path / "backups"),
        dest_dir=str(dest_dir),
        clean=False,
        dry_run=False,
        force=False,
    )

    _, _, metadata, previous, pruned = perform_use(args)
    assert metadata["email"] == "letsmaildhruv@gmail.com"
    assert previous is None
    assert pruned is False
    assert (dest_dir / "auth.json").read_text(encoding="utf-8") == '{"token":"x"}'
    assert (dest_dir / "history.jsonl").read_text(encoding="utf-8") == "runtime"
    assert (dest_dir / "cache").exists()


def test_use_clean_mode_prunes_then_restores(tmp_path: Path) -> None:
    create_sample_backup(tmp_path)
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    (dest_dir / "auth.json").write_text("old", encoding="utf-8")
    (dest_dir / "history.jsonl").write_text("runtime", encoding="utf-8")
    (dest_dir / "cache").mkdir()

    args = SimpleNamespace(
        from_archive=None,
        email="letsmaildhruv@gmail.com",
        backup_dir=str(tmp_path / "backups"),
        dest_dir=str(dest_dir),
        clean=True,
        dry_run=False,
        force=False,
    )

    _, _, _, _, pruned = perform_use(args)
    assert pruned is True
    assert (dest_dir / "auth.json").read_text(encoding="utf-8") == '{"token":"x"}'
    assert not (dest_dir / "cache").exists()
