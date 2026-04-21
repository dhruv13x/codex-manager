from __future__ import annotations

import json
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from .prune import perform_prune
from .status import (
    LiveStatus,
    capture_tmux_status_text,
    parse_live_status_text,
    run_status_command,
)
from .utils import build_archive_name, isoformat_local

EXCLUDED_TOP_LEVEL_NAMES = {".tmp", "tmp"}
AUTH_ONLY_INCLUDES = {"auth.json", "config.toml", "installation_id"}


def read_status_text_from_args(args) -> str:
    if getattr(args, "status_file", None):
        return Path(args.status_file).read_text(encoding="utf-8")

    if getattr(args, "status_command", None):
        return run_status_command(args.status_command)

    return capture_tmux_status_text(
        session_name=args.tmux_session_name,
        codex_command=args.codex_command,
        cols=args.tmux_cols,
        rows=args.tmux_rows,
        startup_timeout_seconds=args.startup_timeout_seconds,
        status_timeout_seconds=args.status_timeout_seconds,
    )


def build_backup_metadata(
    status: LiveStatus,
    source_dir: Path,
    archive_path: Path,
    *,
    backup_mode: str = "full",
    pruned_before_backup: bool = False,
) -> dict:
    return {
        "product": "codex",
        "email": status.email,
        "session_start_at": isoformat_local(status.session_start_at),
        "next_available_at": isoformat_local(status.reset_at),
        "reset_at": isoformat_local(status.reset_at),
        "quota_text": status.quota_text,
        "quota_percent_left": status.quota_percent_left,
        "archive_name": archive_path.name,
        "archive_path": str(archive_path),
        "source_codex_home": str(source_dir),
        "created_at": isoformat_local(datetime.now().astimezone()),
        "status_source": "live_codex_status",
        "is_expired": getattr(status, "is_expired", False),
        "backup_mode": backup_mode,
        "pruned_before_backup": pruned_before_backup,
    }


def iter_source_entries(source_dir: Path, include_tmp: bool, auth_only: bool) -> list[Path]:
    entries = []
    for path in sorted(source_dir.iterdir(), key=lambda item: item.name):
        if auth_only and path.name not in AUTH_ONLY_INCLUDES:
            continue
        if not include_tmp and path.name in EXCLUDED_TOP_LEVEL_NAMES:
            continue
        entries.append(path)
    return entries


def create_backup_archive(
    source_dir: Path,
    archive_path: Path,
    metadata_path: Path,
    metadata: dict,
    *,
    include_tmp: bool,
    auth_only: bool,
) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="codex-manager-backup-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        temp_metadata_path = temp_dir / metadata_path.name
        temp_metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        with tarfile.open(archive_path, "w:gz") as tar:
            for path in iter_source_entries(source_dir, include_tmp, auth_only):
                tar.add(path, arcname=path.name, recursive=True)
            tar.add(temp_metadata_path, arcname=temp_metadata_path.name, recursive=False)


def perform_backup(args) -> tuple[Path, Path, dict]:
    source_dir = Path(args.source_dir).expanduser()
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source Codex directory does not exist: {source_dir}")

    pruned = False
    if getattr(args, "prune_first", False):
        from types import SimpleNamespace

        prune_args = SimpleNamespace(source_dir=str(source_dir), dry_run=args.dry_run)
        perform_prune(prune_args)
        pruned = True

    live_status = None
    
    if getattr(args, "without_status_check", False):
        # Fallback: Identify current email from auth.json
        auth_path = source_dir / "auth.json"
        current_email = "unknown"
        if auth_path.exists():
            try:
                auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
                current_email = auth_data.get("email", "unknown")
            except Exception:
                pass
        
        from .status import LiveStatus
        now = datetime.now().astimezone()
        
        # Next-Gen Upgrade: Assume account was just exhausted.
        # Quota resets weekly, so next available is +7 days.
        session_start_at = now
        reset_at = now + timedelta(days=7)
        
        live_status = LiveStatus(
            email=current_email,
            reset_at=reset_at,
            session_start_at=session_start_at,
            quota_text="Status capture bypassed via --without-status-check. Estimated +7 days cooldown.",
            quota_percent_left=None,
            proposed_archive_name=build_archive_name(reset_at, current_email),
        )
        from .ui import console
        console.print(f"[yellow]Warning:[/] Using Next-Gen Safety Fallback (+7 days): {live_status.proposed_archive_name}")
    else:
        # Strict Status Check: Retry logic: up to 2 attempts
        from .status import TokenExpiredError
        for attempt in range(1, 3):
            try:
                status_text = read_status_text_from_args(args)
                live_status = parse_live_status_text(
                    status_text,
                    reference_year=args.reference_year,
                )
                break
            except TokenExpiredError as e:
                from .ui import console
                console.print(f"[bold red]Error:[/] {e}")
                # We can't take a backup if token is expired, but let's at least update metadata
                try:
                    status = parse_live_status_text(e.output)
                    from .account_status import patch_metadata
                    patch_metadata(
                        email=status.email,
                        reset_at=status.reset_at,
                        quota_text="TOKEN EXPIRED: Re-login required.",
                        quota_percent_left=None,
                        args=args,
                        session_start_at=status.session_start_at,
                    )
                except Exception:
                    pass
                sys.exit(1)
            except Exception as e:
                from .ui import console
                if attempt == 1:
                    console.print(f"[yellow]Status capture failed (attempt 1): {e}. Try one more time...[/]")
                else:
                    console.print(f"[bold red]Error:[/] Status capture failed twice: {e}")
                    console.print("\n[bold yellow]Next-Gen Safety Protocol:[/]")
                    console.print("If Codex has changed its layout or status is unavailable, you MUST use:")
                    console.print(f"  [bright_cyan]cm {args.command} --without-status-check ...[/]")
                    console.print("[dim]This will safely assume a 7-day cooldown for the current account.[/]")
                    sys.exit(1)

    # In case of logic errors, ensure live_status exists
    if not live_status:
         console.print("[bold red]Error:[/] Could not resolve status and no fallback was triggered.")
         sys.exit(1)

    backup_dir = Path(args.backup_dir).expanduser()
    archive_path = backup_dir / live_status.proposed_archive_name
    metadata_path = backup_dir / live_status.proposed_archive_name.replace(
        ".tar.gz", ".metadata.json"
    )

    backup_mode = "auth-only" if getattr(args, "auth_only", False) else "full"

    metadata = build_backup_metadata(
        live_status,
        source_dir,
        archive_path,
        backup_mode=backup_mode,
        pruned_before_backup=pruned,
    )

    if args.dry_run:
        return archive_path, metadata_path, metadata

    if archive_path.exists() and not args.force:
        raise FileExistsError(
            f"Archive already exists: {archive_path}. Use --force to overwrite."
        )

    if archive_path.exists():
        archive_path.unlink()
    if metadata_path.exists():
        metadata_path.unlink()

    create_backup_archive(
        source_dir,
        archive_path,
        metadata_path,
        metadata,
        include_tmp=args.include_tmp,
        auth_only=getattr(args, "auth_only", False),
    )
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    latest_path = backup_dir / f"{live_status.email}-latest-codex.tar.gz"
    if latest_path.exists() or latest_path.is_symlink():
        latest_path.unlink()
    latest_path.symlink_to(archive_path.name)

    from .registry import update_registry_entry
    update_registry_entry(
        email=live_status.email,
        reset_at=live_status.reset_at,
        is_expired=getattr(live_status, "is_expired", False),
        quota_text=live_status.quota_text,
        quota_percent_left=live_status.quota_percent_left,
        session_start_at=live_status.session_start_at,
    )

    return archive_path, metadata_path, metadata


def backup_result_to_text(archive_path: Path, metadata_path: Path, metadata: dict, *, dry_run: bool) -> str:
    lines = [
        f"mode: {'dry-run' if dry_run else 'created'}",
        f"archive: {archive_path}",
        f"metadata: {metadata_path}",
        f"email: {metadata['email']}",
        f"session_start_at: {metadata['session_start_at']}",
        f"reset_at: {metadata['reset_at']}",
        f"quota_text: {metadata['quota_text']}",
    ]
    return "\n".join(lines)
