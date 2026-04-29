from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .backup import read_status_text_from_args
from .cloud import get_cloud_provider
from .list_backups import list_cloud_backups
from .registry import sync_registry_with_cloud, update_registry_entry
from .ui import console
from .utils import build_archive_name


def patch_metadata(
    email: str,
    reset_at: Any | None = None,
    quota_text: str | None = None,
    quota_percent_left: int | None = None,
    args: Any = None,
    session_start_at: Any | None = None,
    is_expired: bool = False,
    dry_run: bool = False,
) -> None:
    backup_dir = Path(args.backup_dir).expanduser() if args and hasattr(args, "backup_dir") else Path("~/.codex-manager/backups").expanduser()
    
    # We will compute the final reset_at and session_start_at to save to registry
    final_reset_at = reset_at
    final_session_start_at = session_start_at
    if is_expired and final_reset_at is None:
        final_reset_at = datetime.now().astimezone()
    if is_expired and final_session_start_at is None and final_reset_at is not None:
        final_session_start_at = final_reset_at - timedelta(days=7)

    if backup_dir.exists():
        # Find any metadata file containing this email
        metadata_paths = []
        for p in backup_dir.glob("*.metadata.json"):
            if email in p.name:
                 metadata_paths.append(p)
        
        if metadata_paths:
            # Sort by name descending to get the latest
            metadata_paths.sort(key=lambda p: p.name, reverse=True)
            metadata_path = metadata_paths[0]
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                
                if reset_at is not None:
                    data["reset_at"] = (
                        reset_at.isoformat() if hasattr(reset_at, "isoformat") else str(reset_at)
                    )
                    data["next_available_at"] = data["reset_at"]
                
                if session_start_at is not None:
                    data["session_start_at"] = (
                        session_start_at.isoformat()
                        if hasattr(session_start_at, "isoformat")
                        else str(session_start_at)
                    )
                
                # capture the final values from existing metadata if we didn't overwrite
                if final_reset_at is None and "reset_at" in data:
                    from .cooldown import parse_iso_datetime
                    try:
                        final_reset_at = parse_iso_datetime(data["reset_at"])
                    except Exception:
                        pass
                if final_session_start_at is None and "session_start_at" in data:
                    from .cooldown import parse_iso_datetime
                    try:
                        final_session_start_at = parse_iso_datetime(data["session_start_at"])
                    except Exception:
                        pass

                if quota_text is not None:
                    data["quota_text"] = quota_text
                if quota_percent_left is not None:
                    data["quota_percent_left"] = quota_percent_left
                data["is_expired"] = is_expired
                data["updated_at"] = datetime.now().astimezone().isoformat()
                if not dry_run:
                    metadata_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    console.print(
                        f"Updated local metadata for [cyan]{email}[/]: [dim]{metadata_path.name}[/]"
                    )
                else:
                    console.print(f"Would update local metadata for [cyan]{email}[/]: [dim]{metadata_path.name}[/]")
            except Exception as exc:
                console.print(f"[yellow]Warning:[/] Failed to patch local metadata: {exc}")
        else:
            now = datetime.now().astimezone()
            final_reset_at = reset_at or now
            final_session_start_at = session_start_at or (now - timedelta(days=7))
            archive_name = build_archive_name(final_reset_at, email)
            metadata_path = backup_dir / archive_name.replace(".tar.gz", ".metadata.json")
            data = {
                "product": "codex",
                "email": email,
                "session_start_at": (
                    final_session_start_at.isoformat()
                    if hasattr(final_session_start_at, "isoformat")
                    else str(final_session_start_at)
                ),
                "next_available_at": (
                    final_reset_at.isoformat() if hasattr(final_reset_at, "isoformat") else str(final_reset_at)
                ),
                "reset_at": (
                    final_reset_at.isoformat() if hasattr(final_reset_at, "isoformat") else str(final_reset_at)
                ),
                "quota_text": quota_text or "unknown",
                "quota_percent_left": quota_percent_left,
                "is_expired": is_expired,
                "archive_name": archive_name,
                "created_at": now.isoformat(),
                "status_source": "pre_switch_sync",
                "metadata_only": True,
            }
            try:
                if not dry_run:
                    metadata_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    console.print(
                        f"Created cooldown-only metadata for [cyan]{email}[/]: [dim]{metadata_path.name}[/]"
                    )
                else:
                    console.print(f"Would create cooldown-only metadata for [cyan]{email}[/]: [dim]{metadata_path.name}[/]")
            except Exception as exc:
                console.print(f"[yellow]Warning:[/] Failed to create local metadata: {exc}")

    update_registry_entry(
        email=email,
        reset_at=final_reset_at,
        is_expired=is_expired,
        quota_text=quota_text,
        quota_percent_left=quota_percent_left,
        session_start_at=final_session_start_at,
        dry_run=dry_run,
    )

    if args and getattr(args, "cloud", False):
        cp = get_cloud_provider(args)
        if cp:
            sync_registry_with_cloud(cp, dry_run=dry_run)
            entries = list_cloud_backups(cp, email=email, latest_per_email=True)
            if entries:
                selected = entries[0]
                archive_name = selected.archive_path.name
                metadata_name = archive_name.replace(".tar.gz", ".metadata.json")

                with tempfile.TemporaryDirectory() as tmp:
                    local_metadata = Path(tmp) / metadata_name
                    try:
                        cp.download_file(metadata_name, local_metadata)
                        data = json.loads(local_metadata.read_text(encoding="utf-8"))
                        if final_reset_at is not None:
                            data["reset_at"] = (
                                final_reset_at.isoformat() if hasattr(final_reset_at, "isoformat") else str(final_reset_at)
                            )
                            data["next_available_at"] = data["reset_at"]
                        if final_session_start_at:
                            data["session_start_at"] = (
                                final_session_start_at.isoformat()
                                if hasattr(final_session_start_at, "isoformat")
                                else str(final_session_start_at)
                            )
                        data["quota_text"] = quota_text
                        if quota_percent_left is not None:
                            data["quota_percent_left"] = quota_percent_left
                        data["is_expired"] = is_expired
                        data["updated_at"] = datetime.now().astimezone().isoformat()
                        local_metadata.write_text(json.dumps(data, indent=2), encoding="utf-8")

                        if not dry_run:
                            console.print(
                                f"Uploading updated metadata to Cloud: [dim]{metadata_name}[/] ..."
                            )
                            cp.upload_file(local_metadata, metadata_name)
                            console.print("Cloud metadata update complete.")
                        else:
                            console.print(f"Would upload updated metadata to Cloud: [dim]{metadata_name}[/]")
                    except Exception as exc:
                        console.print(f"[yellow]Warning:[/] Failed to patch cloud metadata: {exc}")
        else:
            console.print("[yellow]Warning:[/] Cloud update requested but credentials not resolved.")


def sync_current_account_status(args: Any) -> None:
    codex_home = Path(
        getattr(
            args,
            "dest_dir",
            args.source_dir if hasattr(args, "source_dir") else "~/.codex",
        )
    ).expanduser()
    auth_path = codex_home / "auth.json"

    current_email = None
    if auth_path.exists():
        try:
            auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
            current_email = auth_data.get("email")
        except Exception:
            pass

    if getattr(args, "without_status_check", False):
        if not current_email:
            console.print(
                "[yellow]Warning:[/] Could not identify current account from auth.json. "
                "Skipping pre-switch status sync."
            )
            return
        now = datetime.now().astimezone()
        session_start_at = now
        reset_at = now + timedelta(days=7)

        console.print(f"[yellow]Note:[/] Bypassing status check for [cyan]{current_email}[/].")
        console.print(
            "[yellow]Assuming exhaustion:[/] Next reset estimated for "
            f"[bright_magenta]{reset_at.strftime('%Y-%m-%d %H:%M:%S')}[/]"
        )

        patch_metadata(
            email=current_email,
            reset_at=reset_at,
            quota_text="Status capture bypassed via --without-status-check. Estimated +7 days cooldown.",
            quota_percent_left=None,
            args=args,
            session_start_at=session_start_at,
            dry_run=getattr(args, "dry_run", False),
        )
        args.current_account_email = current_email
        return

    if current_email:
        console.print(f"Syncing status for current account: [cyan]{current_email}[/]")
    else:
        console.print("Syncing status for current live account...")

    text = None
    from .status import TokenExpiredError
    for attempt in range(1, 3):
        try:
            text = read_status_text_from_args(args)
            if text:
                break
        except TokenExpiredError as exc:
            console.print(f"[bold red]Error:[/] {exc}")
            # Try to at least get the email from the error output
            try:
                from .status import parse_live_status_text
                status = parse_live_status_text(exc.output)
                patch_metadata(
                    email=status.email,
                    reset_at=None,
                    quota_text="TOKEN EXPIRED: Re-login required.",
                    quota_percent_left=None,
                    args=args,
                    session_start_at=None,
                    is_expired=True,
                    dry_run=getattr(args, "dry_run", False),
                )
                args.current_account_email = status.email
            except Exception:
                if current_email:
                    patch_metadata(
                        email=current_email,
                        reset_at=None,
                        quota_text="TOKEN EXPIRED: Re-login required.",
                        quota_percent_left=None,
                        args=args,
                        is_expired=True,
                        dry_run=getattr(args, "dry_run", False),
                    )
                    args.current_account_email = current_email
                else:
                    console.print(
                        "[bold red]Error:[/] Could not identify current account from live status or auth.json."
                    )
                    console.print("[dim]Use --without-status-check only when auth.json contains the active email.[/]")
            sys.exit(1)
        except Exception as exc:
            if attempt == 1:
                console.print(f"[yellow]Status capture failed (attempt 1): {exc}. Try one more time...[/]")
            else:
                account_label = current_email or "current live account"
                console.print(
                    f"[bold red]Error:[/] Status capture failed twice for [cyan]{account_label}[/]: {exc}"
                )
                console.print("\n[bold yellow]Next-Gen Safety Protocol:[/]")
                console.print("If Codex has changed its layout or status is unavailable, you MUST use:")
                console.print(f"  [bright_cyan]cm {args.command} --without-status-check ...[/]")
                console.print("[dim]This will safely assume a 7-day cooldown for the current account.[/]")
                sys.exit(1)

    if text:
        try:
            from .status import parse_live_status_text
            status = parse_live_status_text(
                text,
                reference_year=getattr(args, "reference_year", None),
            )
            patch_metadata(
                email=status.email,
                reset_at=status.reset_at,
                quota_text=status.quota_text,
                quota_percent_left=status.quota_percent_left,
                args=args,
                session_start_at=status.session_start_at,
                is_expired=status.is_expired,
                dry_run=getattr(args, "dry_run", False),
            )
            args.current_account_email = status.email
        except Exception as exc:
            account_label = current_email or "current live account"
            console.print(
                f"[bold red]Error:[/] Failed to parse status for [cyan]{account_label}[/]: {exc}"
            )
            console.print("[dim]Use --without-status-check if Codex layout has changed.[/]")
            sys.exit(1)
