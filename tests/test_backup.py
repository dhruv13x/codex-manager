from __future__ import annotations

import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

from codex_manager.backup import perform_backup


def make_args(tmp_path: Path, source_dir: Path, status_file: Path, *, dry_run: bool = False):
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
        dry_run=dry_run,
        force=False,
        auth_only=False,
        prune_first=False,
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

    assert archive_path.name == "2026-04-19-100200-letsmaildhruv@gmail.com-codex.tar.gz"
    assert metadata_path.name == "2026-04-19-100200-letsmaildhruv@gmail.com-codex.metadata.json"
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
    assert loaded["email"] == metadata["email"]

    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert "auth.json" in names
    assert "history.jsonl" in names
    assert "tmp/skip.txt" not in names
    assert archive_path.name.replace(".tar.gz", ".metadata.json") in names


def test_backup_auth_only(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex"
    source_dir.mkdir()
    (source_dir / "auth.json").write_text("{}", encoding="utf-8")
    (source_dir / "config.toml").write_text("", encoding="utf-8")
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
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert "auth.json" in names
    assert "config.toml" in names
    assert "history.jsonl" not in names


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
    assert "auth.json" in names
    assert "models_cache.json" not in names
