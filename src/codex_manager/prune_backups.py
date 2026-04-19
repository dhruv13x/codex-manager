from __future__ import annotations

import os
from pathlib import Path
from collections import defaultdict

from .config import DEFAULT_BACKUP_DIR
from .list_backups import iter_backup_archives, build_backup_entry

def perform_prune_backups(
    backup_dir: Path,
    keep: int | None = None,
    keep_latest_per_email: bool = False,
    dry_run: bool = False,
) -> None:
    if keep is None and not keep_latest_per_email:
        print("Nothing to do: must specify --keep or --keep-latest-per-email")
        return

    entries = [build_backup_entry(path) for path in iter_backup_archives(backup_dir)]

    # Sort chronologically, oldest first, for easier reasoning about "latest"
    # Actually, default from iter_backup_archives is reverse=True (newest first). Let's work with newest first.
    entries.sort(key=lambda e: e.created_at, reverse=True)

    to_delete = []

    if keep_latest_per_email:
        seen_emails = set()
        kept = []
        for e in entries:
            if e.email not in seen_emails:
                seen_emails.add(e.email)
                kept.append(e)
            else:
                to_delete.append(e)
        entries = kept

    if keep is not None:
        if len(entries) > keep:
            to_delete.extend(entries[keep:])
            entries = entries[:keep]

    if not to_delete:
        print("No backups matched pruning criteria.")
        return

    for entry in to_delete:
        if dry_run:
            print(f"Would delete {entry.archive_path.name}")
            metadata_path = entry.archive_path.with_name(entry.archive_path.name.replace(".tar.gz", ".metadata.json"))
            if metadata_path.exists():
                print(f"Would delete {metadata_path.name}")
            continue

        print(f"Deleting {entry.archive_path.name}...")
        try:
            entry.archive_path.unlink()
            metadata_path = entry.archive_path.with_name(entry.archive_path.name.replace(".tar.gz", ".metadata.json"))
            if metadata_path.exists():
                metadata_path.unlink()
        except OSError as err:
            print(f"Failed to delete {entry.archive_path.name}: {err}")
