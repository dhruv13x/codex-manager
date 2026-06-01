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
    is_expired: bool | None = None,
    dry_run: bool = False,
) -> None:
    backup_dir = Path(args.backup_dir).expanduser() if args and hasattr(args, "backup_dir") else Path("~/.codex-manager/backups").expanduser()
    
    # Track the effective is_expired state to use for registry sync
    from .registry import get_registry_entry
    existing = get_registry_entry(email)
    existing_is_expired = False
    if existing and existing.get("is_expired"):
        existing_is_expired = True

    # Find if the existing local metadata also indicates expired
    if backup_dir.exists():
        metadata_paths = []
        for p in backup_dir.glob("*.metadata.json"):
            if email in p.name:
                 metadata_paths.append(p)
        auth_meta = backup_dir / "auth" / email / "latest.metadata.json"
        if auth_meta.exists():
            metadata_paths.append(auth_meta)

        if metadata_paths:
            for p in metadata_paths:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("is_expired"):
                        existing_is_expired = True
                        break
                except Exception:
                    pass

    if existing_is_expired:
        is_successful_sync = False
        if quota_text:
            text_lower = quota_text.lower()
            if not ("bypassed" in text_lower or "failed" in text_lower or "expired" in text_lower or "login" in text_lower or "unauthorized" in text_lower or "refresh" in text_lower or "available" in text_lower):
                is_successful_sync = True
        if is_expired is True:
            effective_is_expired = True
        elif is_expired is False:
            effective_is_expired = False if is_successful_sync else True
        else: # is_expired is None
            effective_is_expired = True
    else:
        effective_is_expired = is_expired if is_expired is not None else False

    # We will compute the final reset_at and session_start_at to save to registry
    final_reset_at = reset_at
    final_session_start_at = session_start_at
    
    # If is_expired is not provided, we might need to check the current state 
    # but we can do a preliminary check for the explicit 'True' case.
    if is_expired is True and final_reset_at is None:
        final_reset_at = datetime.now().astimezone()
    if is_expired is True and final_session_start_at is None and final_reset_at is not None:
        final_session_start_at = final_reset_at - timedelta(days=7)

    if backup_dir.exists():
        # Find any metadata file containing this email
        metadata_paths = []
        for p in backup_dir.glob("*.metadata.json"):
            if email in p.name:
                 metadata_paths.append(p)
        auth_meta = backup_dir / "auth" / email / "latest.metadata.json"
        if auth_meta.exists():
            metadata_paths.append(auth_meta)
        
        if metadata_paths:
            for metadata_path in metadata_paths:
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
                    
                    data["is_expired"] = effective_is_expired
                    
                    data["updated_at"] = datetime.now().astimezone().isoformat()
                    if not dry_run:
                        metadata_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        console.print(
                            f"Updated local metadata for [cyan]{email}[/]: [dim]{metadata_path.name}[/]"
                        )
                    else:
                        console.print(f"Would update local metadata for [cyan]{email}[/]: [dim]{metadata_path.name}[/]")
                except Exception as exc:
                    console.print(f"[yellow]Warning:[/] Failed to patch local metadata for [dim]{metadata_path.name}[/]: {exc}")
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
                "is_expired": effective_is_expired,
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

    from .utils import extract_jwt_details
    codex_home = Path(getattr(args, "source_dir", None) or getattr(args, "dest_dir", None) or "~/.codex").expanduser()
    jwt_details = extract_jwt_details(codex_home / "auth.json")

    update_registry_entry(
        email=email,
        reset_at=final_reset_at,
        is_expired=effective_is_expired,
        quota_text=quota_text,
        quota_percent_left=quota_percent_left,
        session_start_at=final_session_start_at,
        dry_run=dry_run,
        plan_type=jwt_details.get("plan_type"),
        id_token_expires_at=jwt_details.get("id_token_expires_at"),
        access_token_expires_at=jwt_details.get("access_token_expires_at"),
        auth_expires_at=jwt_details.get("auth_expires_at"),
        auth_provider=jwt_details.get("auth_provider"),
        has_refresh_token=jwt_details.get("has_refresh_token"),
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

    if not auth_path.exists():
        console.print("[yellow]Note:[/] No active session (auth.json missing). Skipping pre-switch status sync.")
        return

    from .registry import get_active_account
    current_email = get_active_account()

    if not current_email and auth_path.exists():
        from .utils import extract_email_from_auth_json
        current_email = extract_email_from_auth_json(auth_path)

    if getattr(args, "without_status_check", False):
        if not current_email:
            console.print(
                "[yellow]Warning:[/] Could not identify current account from auth.json. "
                "Skipping pre-switch status sync."
            )
            return
        now = datetime.now().astimezone()

        # Preserve active registry future cooldown if available
        from .registry import get_registry_entry
        reg_entry = get_registry_entry(current_email)
        reg_reset_at = None
        if reg_entry and "reset_at" in reg_entry:
            from .cooldown import parse_iso_datetime
            try:
                reg_reset_at = parse_iso_datetime(reg_entry["reset_at"])
            except Exception:
                pass

        if reg_reset_at and reg_reset_at > now:
            reset_at = reg_reset_at
            session_start_at = parse_iso_datetime(reg_entry.get("session_start_at", now))
            quota_text = reg_entry.get("quota_text") or "Status capture bypassed via --without-status-check. Preserved from active registry."
            quota_percent_left = reg_entry.get("quota_percent_left")
            console.print(f"[yellow]Note:[/] Bypassing status check for [cyan]{current_email}[/].")
            console.print(
                "[yellow]Preserved active registry reset time:[/] Next reset on "
                f"[bright_magenta]{reset_at.strftime('%Y-%m-%d %H:%M:%S')}[/]"
            )
        else:
            session_start_at = now
            reset_at = now + timedelta(days=7)
            quota_text = "Status capture bypassed via --without-status-check. Estimated +7 days cooldown."
            quota_percent_left = None
            console.print(f"[yellow]Note:[/] Bypassing status check for [cyan]{current_email}[/].")
            console.print(
                "[yellow]Assuming exhaustion:[/] Next reset estimated for "
                f"[bright_magenta]{reset_at.strftime('%Y-%m-%d %H:%M:%S')}[/]"
            )

        patch_metadata(
            email=current_email,
            reset_at=reset_at,
            quota_text=quota_text,
            quota_percent_left=quota_percent_left,
            args=args,
            session_start_at=session_start_at,
            is_expired=None,
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
            args.status_confirmed_expired = True
            # Try to at least get the email from the error output
            try:
                from .status import parse_live_status_text
                status = parse_live_status_text(exc.output)
                identified_email = status.email or current_email
                if identified_email:
                    patch_metadata(
                        email=identified_email,
                        reset_at=None,
                        quota_text="TOKEN EXPIRED: Re-login required.",
                        quota_percent_left=None,
                        args=args,
                        session_start_at=None,
                        is_expired=True,
                        dry_run=getattr(args, "dry_run", False),
                    )
                    args.current_account_email = identified_email
                else:
                    raise ValueError("Could not identify account from status or auth.json")
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
            if getattr(args, "command", None) == "status":
                sys.exit(1)
            return
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
        args.captured_status_text = text
        try:
            from .status import parse_live_status_text
            status = parse_live_status_text(
                text,
                reference_year=getattr(args, "reference_year", None),
            )
            identified_email = status.email or current_email
            if not identified_email:
                  raise ValueError("Could not identify account email from status or auth.json")

            patch_metadata(
                email=identified_email,
                reset_at=status.reset_at,
                quota_text=status.quota_text,
                quota_percent_left=status.quota_percent_left,
                args=args,
                session_start_at=status.session_start_at,
                is_expired=status.is_expired,
                dry_run=getattr(args, "dry_run", False),
            )
            args.current_account_email = identified_email
        except Exception as exc:
            account_label = current_email or "current live account"
            console.print(
                f"[bold red]Error:[/] Failed to parse status for [cyan]{account_label}[/]: {exc}"
            )
            console.print("[dim]Use --without-status-check if Codex layout has changed.[/]")
            sys.exit(1)
