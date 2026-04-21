from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .cooldown import evaluate_records
from .prune import perform_prune
from .recommend import choose_best_account
from .restore import perform_restore


def perform_use(args: Any) -> tuple[Path, Path, dict[str, Any], Path | None, bool]:
    """
    High-level workflow for switching accounts.
    If no identity (email or archive) is provided, it automatically recommends the best one.
    """
    dest_dir = Path(args.dest_dir).expanduser()
    pruned = False

    # 1. Identity Resolution: If no email/archive, recommend the best account
    if not args.email and not args.from_archive:
        # We need a list of entries to recommend from
        # Note: If this is a cloud-recommendation, cli.py should have already 
        # populated args.from_archive or we might need to pass entries in.
        # For now, let's assume local unless cli.py handles the download.
        from .cli import list_entries_from_args
        entries = list_entries_from_args(args)
        if not entries:
            raise ValueError("No backups available to recommend an account from.")
        
        # Build a temporary live status if needed? 
        # (Simplified: just recommend from entries)
        recommendation = choose_best_account(evaluate_records(entries))
        print(f"Automatically recommended: {recommendation.selected.email}")
        args.email = recommendation.selected.email

    # 2. Pre-Restore: Prune if requested
    if getattr(args, "clean", False):
        prune_args = SimpleNamespace(
            source_dir=str(dest_dir),
            dry_run=args.dry_run,
        )
        if dest_dir.exists():
            perform_prune(prune_args)
        pruned = True

    # 3. Execution: Delegate to perform_restore
    # 'use' defaults to auth-only restore unless --clean is requested.
    if not getattr(args, "clean", False):
        args.auth_only = True
    
    archive_path, restored_dest_dir, metadata, existing_backup_path = perform_restore(args)
    
    return archive_path, restored_dest_dir, metadata, existing_backup_path, pruned

def use_result_to_text(
    archive_path: Path,
    dest_dir: Path,
    metadata: dict[str, Any],
    existing_backup_path: Path | None,
    *,
    dry_run: bool,
    pruned: bool,
) -> Any:
    from .rich_utils import create_table

    headers = ["Field", "Value"]
    rows = [
        ["Mode", f"[bold yellow]{'dry-run'}[/]" if dry_run else "[bold green]used[/]"],
        ["Clean State", "yes" if pruned else "no"],
        ["Archive", str(archive_path)],
        ["Destination", str(dest_dir)],
        ["Email", metadata.get("email", "unknown")],
        ["Session Start", metadata.get("session_start_at", "unknown")],
        ["Reset At", metadata.get("reset_at", "unknown")],
    ]
    if existing_backup_path:
        rows.append(["Safety Backup", str(existing_backup_path)])

    return create_table(title="Account Switched Successfully", headers=headers, rows=rows)
