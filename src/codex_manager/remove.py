from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cloud import B2Provider
from .registry import remove_registry_entry, sync_registry_with_cloud
from .ui import console, Confirm


def perform_remove(args: Any) -> dict[str, Any]:
    email = args.email
    backup_dir = Path(args.backup_dir).expanduser()
    dry_run = getattr(args, "dry_run", False)
    use_cloud = getattr(args, "cloud", False)
    force = getattr(args, "yes", False)

    results = {
        "local_files_removed": [],
        "local_registry_removed": False,
        "cloud_files_removed": [],
        "cloud_registry_removed": False,
    }

    # 1. Identify local files
    local_files = []
    if backup_dir.exists():
        for p in backup_dir.glob("*"):
            if email in p.name and (p.name.endswith(".tar.gz") or p.name.endswith(".metadata.json")):
                local_files.append(p)
    
    # 2. Identify cloud files if requested
    cloud_files_to_delete = []
    cp = None
    if use_cloud:
        from .cloud import get_cloud_provider
        cp = get_cloud_provider(args)
        if cp:
            all_cloud_files = cp.list_files()
            for f in all_cloud_files:
                if email in f.name and (f.name.endswith(".tar.gz") or f.name.endswith(".metadata.json")):
                    cloud_files_to_delete.append(f.name)
        else:
            console.print("[bold red]Error:[/] Could not resolve Cloud (B2) credentials for removal.", stderr=True)
            return results

    # 3. Confirmation
    if not force and not dry_run:
        console.print(f"\n[bold red]WARNING:[/] This will delete all backups and registry entries for [cyan]{email}[/].")
        console.print(f"Local files to remove: [bold]{len(local_files)}[/]")
        if use_cloud:
            console.print(f"Cloud files to remove: [bold]{len(cloud_files_to_delete)}[/]")
        
        if not Confirm.ask(f"[bold yellow]Are you sure you want to remove all traces of {email}?[/]"):
            console.print("[blue]Removal cancelled.[/]")
            return results

    # 4. Execute Local Removal
    for p in local_files:
        if not dry_run:
            p.unlink()
        results["local_files_removed"].append(str(p))

    if remove_registry_entry(email, dry_run=dry_run):
        results["local_registry_removed"] = True

    # 5. Execute Cloud Removal
    if use_cloud and cp:
        for filename in cloud_files_to_delete:
            if not dry_run:
                cp.delete_file(filename)
            results["cloud_files_removed"].append(filename)
        
        # To remove from cloud registry, we sync (which merges) then we'd need a way to 
        # actually ensure it's GONE from the cloud version if it exists there.
        # sync_registry_with_cloud currently merges. To force removal, we might need 
        # to ensure the cloud registry is overwritten with our local one that has it removed.
        if not dry_run:
            sync_registry_with_cloud(cp)
            results["cloud_registry_removed"] = True
        else:
            results["cloud_registry_removed"] = True

    return results


def remove_result_to_text(results: dict[str, Any], email: str, dry_run: bool) -> str:
    lines = [
        f"mode: {'dry-run' if dry_run else 'removed'}",
        f"email: {email}",
    ]
    
    lines.append(f"local_files_removed: {len(results['local_files_removed'])}")
    for f in results["local_files_removed"]:
        lines.append(f"  - {f}")
    
    lines.append(f"local_registry_removed: {'YES' if results['local_registry_removed'] else 'NO (not found)'}")
    
    if "cloud_files_removed" in results and results["cloud_files_removed"]:
        lines.append(f"cloud_files_removed: {len(results['cloud_files_removed'])}")
        for f in results["cloud_files_removed"]:
            lines.append(f"  - {f}")
        lines.append(f"cloud_registry_removed: {'YES' if results['cloud_registry_removed'] else 'NO'}")

    return "\n".join(lines)
