from __future__ import annotations

import shutil
from pathlib import Path
from .ui import console, Confirm

def clear_directory_recursively(path: Path) -> None:
    """Recursively deletes all files and subdirectories under path.
    If a subdirectory cannot be deleted (e.g. it is a mount point or locked),
    it recursively clears its contents instead of failing.
    """
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            try:
                shutil.rmtree(child)
            except Exception:
                clear_directory_recursively(child)
        else:
            try:
                child.unlink()
            except Exception:
                pass

def perform_purge(args) -> bool:
    source_dir = Path(args.source_dir).expanduser()
    
    if not source_dir.exists():
        console.print(f"[yellow]Note:[/] Codex directory does not exist: [dim]{source_dir}[/]")
        return False

    if not args.yes and not args.dry_run:
        console.print(f"\n[bold red]WARNING:[/] This will COMPLETELY DELETE [cyan]{source_dir}[/]")
        console.print("[red]This includes your authentication, session history, and all account identity files.[/]")
        if not Confirm.ask("[bold yellow]Are you sure you want to proceed with the purge?[/]"):
            console.print("[blue]Purge cancelled.[/]")
            return False

    if args.dry_run:
        console.print(f"[bold yellow]Dry-run:[/] Would completely remove [cyan]{source_dir}[/]")
        return True

    try:
        if source_dir.is_dir():
            try:
                shutil.rmtree(source_dir)
            except Exception:
                # Robust fallback: recursively clear all contents of the directory
                clear_directory_recursively(source_dir)
        else:
            source_dir.unlink()
        return True
    except Exception as exc:
        console.print(f"[bold red]Error:[/] Failed to purge {source_dir}: {exc}")
        return False

def purge_result_to_text(success: bool, source_dir: Path, dry_run: bool) -> str:
    if not success and not dry_run:
        return "Purge failed or was cancelled."
    
    lines = [
        f"mode: {'dry-run' if dry_run else 'purged'}",
        f"source_dir: {source_dir}",
        f"status: {'SUCCESS' if success else 'SKIPPED'}",
    ]
    if success and not dry_run:
        lines.append("\n[bold green]Codex home has been factory reset.[/]")
        lines.append("Next time you run Codex, it will treat it as a first-time setup.")
    
    return "\n".join(lines)
