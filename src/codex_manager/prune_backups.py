from __future__ import annotations

from pathlib import Path
from typing import Any

from .list_backups import build_backup_entry, iter_backup_archives, list_cloud_backups
from .ui import console
from .cloud import get_cloud_provider

def perform_prune_backups(
    backup_dir: Path,
    keep: int | None = None,
    keep_latest_per_email: bool = False,
    dry_run: bool = False,
    cloud: bool = False,
    args: Any = None,
) -> None:
    if keep is None and not keep_latest_per_email:
        console.print("Nothing to do: must specify --keep or --keep-latest-per-email")
        return

    cp = None
    if cloud:
        cp = get_cloud_provider(args)
        if not cp:
            console.print("[bold red]Error:[/] Could not resolve Cloud (B2) credentials.", style="red", stderr=True)
            return
        # Note: we need all entries to prune accurately, even without email filter
        entries = list_cloud_backups(cp, email=None)
    else:
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
        console.print("No backups matched pruning criteria.")
        return

    for entry in to_delete:
        if cloud:
            archive_name = Path(entry.archive_path).name if isinstance(entry.archive_path, str) else entry.archive_path.name
            metadata_name = archive_name.replace(".tar.gz", ".metadata.json")
            if dry_run:
                console.print(f"Would delete from cloud: {archive_name}")
                console.print(f"Would delete from cloud: {metadata_name}")
            else:
                console.print(f"Deleting from cloud: {archive_name}...")
                try:
                    cp.delete_file(archive_name)
                    cp.delete_file(metadata_name)
                except Exception as e:
                    console.print(f"[bold red]Failed to delete from cloud: {e}[/]", stderr=True)
        else:
            if dry_run:
                console.print(f"Would delete {entry.archive_path.name}")
                metadata_path = entry.archive_path.with_name(entry.archive_path.name.replace(".tar.gz", ".metadata.json"))
                if metadata_path.exists():
                    console.print(f"Would delete {metadata_path.name}")
                continue

            console.print(f"Deleting {entry.archive_path.name}...")
            try:
                entry.archive_path.unlink()
                metadata_path = entry.archive_path.with_name(entry.archive_path.name.replace(".tar.gz", ".metadata.json"))
                if metadata_path.exists():
                    console.print(f"Deleting {metadata_path.name}...")
                    metadata_path.unlink()
            except OSError as e:
                console.print(f"Error deleting file: {e}")
