from __future__ import annotations

import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from .config import DEFAULT_BACKUP_DIR, DEFAULT_CODEX_HOME
from .prune import perform_prune
from .restore import (
    load_metadata_for_archive,
    perform_restore,
    resolve_archive_path,
    validate_archive_contents,
)


def backup_existing_auth(dest_dir: Path) -> Path | None:
    auth_path = dest_dir / "auth.json"
    if not auth_path.exists():
        return None
    backup_path = dest_dir / f"auth.json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(auth_path, backup_path)
    return backup_path


def install_auth_only(archive_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as tar:
        extracted = tar.extractfile("auth.json")
        if extracted is None:
            raise FileNotFoundError(f"Archive does not contain readable auth.json: {archive_path}")
        with tempfile.NamedTemporaryFile(dir=dest_dir, delete=False) as tmp:
            tmp.write(extracted.read())
            tmp_path = Path(tmp.name)
    tmp_path.replace(dest_dir / "auth.json")


def perform_use(args):
    dest_dir = Path(args.dest_dir).expanduser()
    pruned = False

    if args.clean:
        prune_args = SimpleNamespace(
            source_dir=str(dest_dir),
            dry_run=args.dry_run,
        )
        if dest_dir.exists():
            perform_prune(prune_args)
        pruned = True
        restore_args = SimpleNamespace(
            from_archive=args.from_archive,
            email=args.email,
            backup_dir=args.backup_dir,
            dest_dir=args.dest_dir,
            dry_run=args.dry_run,
            force=False,
        )
        archive_path, restored_dest_dir, metadata, existing_backup_path = perform_restore(restore_args)
        return archive_path, restored_dest_dir, metadata, existing_backup_path, pruned

    restore_args = SimpleNamespace(
        from_archive=args.from_archive,
        email=args.email,
        backup_dir=args.backup_dir,
        dest_dir=args.dest_dir,
        dry_run=args.dry_run,
        force=args.force,
    )
    archive_path = resolve_archive_path(restore_args)
    metadata = load_metadata_for_archive(archive_path)
    validate_archive_contents(archive_path)
    existing_backup_path = None

    if not args.dry_run:
        existing_backup_path = backup_existing_auth(dest_dir)
        install_auth_only(archive_path, dest_dir)

    return archive_path, dest_dir, metadata, existing_backup_path, pruned


def use_result_to_text(
    archive_path,
    dest_dir,
    metadata,
    existing_backup_path,
    *,
    dry_run: bool,
    pruned: bool,
) -> str:
    lines = [
        f"mode: {'dry-run' if dry_run else 'used'}",
        f"clean_state: {'yes' if pruned else 'no'}",
        f"archive: {archive_path}",
        f"destination: {dest_dir}",
        f"email: {metadata.get('email', 'unknown')}",
        f"session_start_at: {metadata.get('session_start_at', 'unknown')}",
        f"reset_at: {metadata.get('reset_at', 'unknown')}",
    ]
    if existing_backup_path is not None:
        lines.append(f"previous_destination_backup: {existing_backup_path}")
    lines.append(
        "behavior: "
        + (
            "runtime state was pruned before restore; auth/account state came from the backup"
            if pruned
            else "only auth/account state was swapped; runtime state such as sessions, history, caches, and sqlite files was preserved"
        )
    )
    return "\n".join(lines)
