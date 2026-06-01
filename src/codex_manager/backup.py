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
AUTH_ONLY_INCLUDES = {"auth.json", "config.toml", "installation_id", "version.json", ".personality_migration", "rules"}


def is_auth_file(name: str) -> bool:
    parts = Path(name).parts
    if not parts:
        return False
    return parts[0] in AUTH_ONLY_INCLUDES


def read_status_text_from_args(args) -> str:
    if getattr(args, "captured_status_text", None):
        return args.captured_status_text

    if getattr(args, "status_file", None):
        return Path(args.status_file).read_text(encoding="utf-8")

    if getattr(args, "status_command", None):
        return run_status_command(args.status_command)

    return capture_tmux_status_text(
        session_name=getattr(args, "tmux_session_name", None),
        codex_command=getattr(args, "codex_command", "codex --no-alt-screen"),
        cols=getattr(args, "tmux_cols", 120),
        rows=getattr(args, "tmux_rows", 40),
        startup_timeout_seconds=getattr(args, "startup_timeout_seconds", 20.0),
        status_timeout_seconds=getattr(args, "status_timeout_seconds", 20.0),
    )


def build_backup_metadata(
    status: LiveStatus,
    source_dir: Path,
    archive_path: Path,
    *,
    backup_mode: str = "full",
    pruned_before_backup: bool = False,
) -> dict:
    meta = {
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
    from .utils import extract_jwt_details
    meta.update(extract_jwt_details(source_dir / "auth.json"))
    if status.quota_text and "Status check failed:" in status.quota_text:
        meta["status_error"] = status.quota_text.replace("Status check failed: ", "")
    return meta


def iter_source_entries(source_dir: Path, include_tmp: bool, auth_only: bool, session_only: bool = False) -> list[Path]:
    entries = []
    for path in sorted(source_dir.iterdir(), key=lambda item: item.name):
        is_auth = is_auth_file(path.name)
        if auth_only and not is_auth:
            continue
        if session_only and is_auth:
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
    session_only: bool = False,
) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="codex-manager-backup-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        temp_metadata_path = temp_dir / metadata_path.name
        temp_metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        with tarfile.open(archive_path, "w:gz") as tar:
            for path in iter_source_entries(source_dir, include_tmp, auth_only, session_only):
                tar.add(path, arcname=path.name, recursive=True)
            tar.add(temp_metadata_path, arcname=temp_metadata_path.name, recursive=False)


def perform_backup(args) -> tuple[Path, Path, dict]:
    source_dir = Path(args.source_dir).expanduser()
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source Codex directory does not exist: {source_dir}")

    no_auth = getattr(args, "no_auth", False)
    auth_only = getattr(args, "auth_only", False)
    if no_auth and auth_only:
        raise ValueError("Cannot specify both --auth-only and --no-auth simultaneously.")

    # Fail-Fast: Require auth.json to exist to prevent anonymous/corrupt backups,
    # unless --no-auth is explicitly passed to create a session-only backup.
    auth_path = source_dir / "auth.json"
    if not no_auth and not auth_path.exists():
        raise FileNotFoundError(f"No active session found: 'auth.json' is missing in {source_dir}. Please login to Codex first.")

    pruned = False
    if getattr(args, "prune_first", False):
        from types import SimpleNamespace

        prune_args = SimpleNamespace(source_dir=str(source_dir), dry_run=args.dry_run)
        perform_prune(prune_args)
        pruned = True

    live_status = None
    
    if getattr(args, "without_status_check", False):
        # Fallback: Identify current email from auth.json
        current_email = "unknown"
        if auth_path.exists():
            from .utils import extract_email_from_auth_json
            current_email = extract_email_from_auth_json(auth_path) or "unknown"
        if current_email == "unknown":
            from .registry import get_active_account
            current_email = get_active_account() or "unknown"
        
        from .status import LiveStatus
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
        else:
            session_start_at = now
            reset_at = now + timedelta(days=7)
            quota_text = "Status capture bypassed via --without-status-check. Estimated +7 days cooldown."
            quota_percent_left = None
        
        live_status = LiveStatus(
            email=current_email,
            reset_at=reset_at,
            session_start_at=session_start_at,
            quota_text=quota_text,
            quota_percent_left=quota_percent_left,
            proposed_archive_name=build_archive_name(reset_at, current_email),
        )
        from .ui import console
        if reg_reset_at and reg_reset_at > now:
            console.print(f"[yellow]Warning:[/] Status capture bypassed. Preserving active registry future cooldown: {live_status.proposed_archive_name}")
        else:
            console.print(f"[yellow]Warning:[/] Using Next-Gen Safety Fallback (+7 days): {live_status.proposed_archive_name}")
    else:
        # Strict Status Check: Retry logic: up to 2 attempts, but fallback instead of exit
        from .status import CodexBlockedError, TokenExpiredError
        error_to_save = None
        label = None
        is_expired_state = False

        for attempt in range(1, 3):
            try:
                status_text = read_status_text_from_args(args)
                live_status = parse_live_status_text(
                    status_text,
                    reference_year=args.reference_year,
                )
                break
            except Exception as e:
                # Instant-fail if it is TokenExpiredError or CodexBlockedError on the first attempt
                if attempt == 1 and not isinstance(e, (TokenExpiredError, CodexBlockedError)):
                    from .ui import console
                    console.print(f"[yellow]Status capture failed (attempt 1): {e}. Trying again...[/]")
                    continue
                
                error_to_save = e
                is_expired_state = isinstance(e, TokenExpiredError) or "login" in str(e).lower()
                
                if isinstance(e, TokenExpiredError):
                    label = "expired"
                elif isinstance(e, CodexBlockedError):
                    label = "blocked"
                else:
                    label = "error"
                break
        
        if error_to_save is not None:
            # Fallback: Identify current email from auth.json
            current_email = "unknown"
            if auth_path.exists():
                from .utils import extract_email_from_auth_json
                current_email = extract_email_from_auth_json(auth_path) or "unknown"
            if current_email == "unknown":
                from .registry import get_active_account
                current_email = get_active_account() or "unknown"

            from .status import LiveStatus
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
                quota_text = reg_entry.get("quota_text") or f"Status check failed: {type(error_to_save).__name__}"
                quota_percent_left = reg_entry.get("quota_percent_left")
            else:
                session_start_at = now
                reset_at = now + timedelta(days=7)
                quota_text = f"Status check failed: {type(error_to_save).__name__}"
                quota_percent_left = None

            live_status = LiveStatus(
                email=current_email,
                reset_at=reset_at,
                session_start_at=session_start_at,
                quota_text=quota_text,
                quota_percent_left=quota_percent_left,
                proposed_archive_name=build_archive_name(reset_at, current_email, label=label),
                is_expired=is_expired_state,
            )

            # We can't take a full authenticated status, but let's at least update metadata
            try:
                from .account_status import patch_metadata
                patch_metadata(
                    email=current_email,
                    reset_at=reset_at,
                    quota_text=live_status.quota_text,
                    quota_percent_left=quota_percent_left,
                    args=args,
                    session_start_at=session_start_at,
                    is_expired=is_expired_state,
                )
            except Exception:
                pass
            
            from .ui import console
            console.print(f"[yellow]Warning:[/] Live status check failed/blocked ([red]{type(error_to_save).__name__}: {error_to_save}[/]).")
            if reg_reset_at and reg_reset_at > now:
                console.print(f"[yellow]Proceeding with offline safety fallback, preserving active registry cooldown ({label}):[/] {live_status.proposed_archive_name}")
            else:
                console.print(f"[yellow]Proceeding with offline safety fallback ({label}):[/] {live_status.proposed_archive_name}")

    # In case of logic errors or failed extraction, ensure live_status exists and has email
    if not live_status or not live_status.email or live_status.email == "unknown":
        raise ValueError(f"Could not identify the active account email from auth.json, live status, or active registry in {source_dir}. Please login to Codex first.")

    backup_dir = Path(args.backup_dir).expanduser()
    auth_only = getattr(args, "auth_only", False)

    # 1. Auth Backup Configuration
    auth_subfolder = backup_dir / "auth" / live_status.email
    auth_archive_path = auth_subfolder / "latest.tar.gz"
    auth_metadata_path = auth_subfolder / "latest.metadata.json"

    auth_metadata = build_backup_metadata(
        live_status,
        source_dir,
        auth_archive_path,
        backup_mode="auth-only",
        pruned_before_backup=pruned,
    )

    if auth_only:
        if args.dry_run:
            return auth_archive_path, auth_metadata_path, auth_metadata

        auth_subfolder.mkdir(parents=True, exist_ok=True)
        if auth_archive_path.exists():
            auth_archive_path.unlink()
        if auth_metadata_path.exists():
            auth_metadata_path.unlink()

        create_backup_archive(
            source_dir,
            auth_archive_path,
            auth_metadata_path,
            auth_metadata,
            include_tmp=args.include_tmp,
            auth_only=True,
        )
        auth_metadata_path.write_text(json.dumps(auth_metadata, indent=2), encoding="utf-8")

        # Set up legacy/compatibility symlink
        latest_path = backup_dir / f"{live_status.email}-latest-codex.tar.gz"
        if latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        try:
            # Create a relative symlink pointing to the new auth structure
            latest_path.symlink_to(f"auth/{live_status.email}/latest.tar.gz")
        except OSError:
            pass

        from .registry import update_registry_entry
        update_registry_entry(
            email=live_status.email,
            reset_at=live_status.reset_at,
            is_expired=getattr(live_status, "is_expired", False),
            quota_text=live_status.quota_text,
            quota_percent_left=live_status.quota_percent_left,
            session_start_at=live_status.session_start_at,
            plan_type=auth_metadata.get("plan_type"),
            id_token_expires_at=auth_metadata.get("id_token_expires_at"),
            access_token_expires_at=auth_metadata.get("access_token_expires_at"),
            auth_expires_at=auth_metadata.get("auth_expires_at"),
            auth_provider=auth_metadata.get("auth_provider"),
        )
        return auth_archive_path, auth_metadata_path, auth_metadata

    else:
        # Manual backup: Creates BOTH auth and session backups (auth is skipped if --no-auth is passed)
        # A. Auth Backup
        if not no_auth and not args.dry_run:
            auth_subfolder.mkdir(parents=True, exist_ok=True)
            if auth_archive_path.exists():
                auth_archive_path.unlink()
            if auth_metadata_path.exists():
                auth_metadata_path.unlink()

            create_backup_archive(
                source_dir,
                auth_archive_path,
                auth_metadata_path,
                auth_metadata,
                include_tmp=args.include_tmp,
                auth_only=True,
            )
            auth_metadata_path.write_text(json.dumps(auth_metadata, indent=2), encoding="utf-8")

            # Set up legacy/compatibility symlink
            latest_path = backup_dir / f"{live_status.email}-latest-codex.tar.gz"
            if latest_path.exists() or latest_path.is_symlink():
                latest_path.unlink()
            try:
                latest_path.symlink_to(f"auth/{live_status.email}/latest.tar.gz")
            except OSError:
                pass

        # B. Session-Only Backup
        now_str = live_status.session_start_at.strftime('%Y-%m-%d-%H%M%S')
        session_subfolder = backup_dir / "sessions" / live_status.email
        session_archive_path = session_subfolder / f"backup-{now_str}-codex.tar.gz"
        session_metadata_path = session_subfolder / f"backup-{now_str}-codex.metadata.json"

        session_metadata = build_backup_metadata(
            live_status,
            source_dir,
            session_archive_path,
            backup_mode="session-only",
            pruned_before_backup=pruned,
        )

        if args.dry_run:
            return session_archive_path, session_metadata_path, session_metadata

        session_subfolder.mkdir(parents=True, exist_ok=True)
        create_backup_archive(
            source_dir,
            session_archive_path,
            session_metadata_path,
            session_metadata,
            include_tmp=args.include_tmp,
            auth_only=False,
            session_only=True,
        )
        session_metadata_path.write_text(json.dumps(session_metadata, indent=2), encoding="utf-8")

        from .registry import update_registry_entry
        update_registry_entry(
            email=live_status.email,
            reset_at=live_status.reset_at,
            is_expired=getattr(live_status, "is_expired", False),
            quota_text=live_status.quota_text,
            quota_percent_left=live_status.quota_percent_left,
            session_start_at=live_status.session_start_at,
            plan_type=session_metadata.get("plan_type"),
            id_token_expires_at=session_metadata.get("id_token_expires_at"),
            access_token_expires_at=session_metadata.get("access_token_expires_at"),
            auth_expires_at=session_metadata.get("auth_expires_at"),
            auth_provider=session_metadata.get("auth_provider"),
        )
        return session_archive_path, session_metadata_path, session_metadata


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
