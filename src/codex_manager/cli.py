from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .account_status import patch_metadata, sync_current_account_status
from .args import get_parser
from .backup import backup_result_to_text, perform_backup, read_status_text_from_args
from .cloud import get_cloud_provider
from .cooldown import CooldownStatus, evaluate_records, print_statuses_table
from .doctor import run_doctor
from .list_backups import BackupEntry, list_backups, list_cloud_backups, print_entries_table
from .profile import export_profile, import_profile
from .prune import perform_prune, prune_result_to_text
from .purge import perform_purge, purge_result_to_text
from .remove import perform_remove, remove_result_to_text
from .prune_backups import perform_prune_backups
from .recommend import choose_best_account
from .registry import sync_registry_with_cloud
from .restore import perform_restore, restore_result_to_text
from .status import capture_tmux_status_text, live_status_to_text, parse_live_status_text
from .sync import pull_backup, push_backup
from .ui import console
from .use_account import perform_use, use_result_to_text


def list_entries_from_args(args: Any) -> list[BackupEntry]:
    force_latest = args.command in ["cooldown", "recommend"]
    # For list-backups, it now defaults to True in args.py, but we ensure it here
    latest_per_email = getattr(args, "latest_per_email", True) or force_latest
    all_entries: list[BackupEntry] = []

    backup_dir = Path(args.backup_dir).expanduser()
    if backup_dir.exists():
        all_entries.extend(
            list_backups(
                backup_dir,
                email=getattr(args, "email", None),
                latest_per_email=False,
                ready=getattr(args, "ready", False),
                sort_by=getattr(args, "sort", "created_at"),
            )
        )

    if getattr(args, "cloud", False):
        cp = get_cloud_provider(args)
        if cp:
            # Sync registry (cooldown.json) when cloud is enabled
            sync_registry_with_cloud(cp)

            all_entries.extend(
                list_cloud_backups(
                    cp,
                    email=getattr(args, "email", None),
                    latest_per_email=False,
                    ready=getattr(args, "ready", False),
                    sort_by=getattr(args, "sort", "created_at"),
                )
            )
        elif getattr(args, "cloud", False):
            console.print(
                "[bold red]Error:[/] Could not resolve Cloud (B2) credentials.",
                style="red",
                stderr=True,
            )
            sys.exit(1)

    if latest_per_email:
        # Sort by reset_at descending so the newest state is picked
        all_entries.sort(key=lambda entry: entry.reset_at, reverse=True)
        seen_emails: dict[str, BackupEntry] = {}
        for entry in all_entries:
            if entry.email not in seen_emails:
                seen_emails[entry.email] = entry
            else:
                existing = seen_emails[entry.email]
                if existing.source != entry.source:
                    seen_emails[entry.email] = replace(existing, source="both")
        return list(seen_emails.values())

    return all_entries


def _ensure_cloud_archive(args: Any) -> None:
    if not getattr(args, "cloud", False) or getattr(args, "from_archive", None):
        return

    cp = get_cloud_provider(args)
    if not cp:
        console.print(
            "[bold red]Error:[/] Could not resolve Cloud (B2) credentials.",
            style="red",
            stderr=True,
        )
        sys.exit(1)

    email = getattr(args, "email", None)
    if not email and args.command == "use":
        entries = list_cloud_backups(cp, latest_per_email=True)
        if not entries:
            console.print("[bold red]Error:[/] No backups found in Cloud.", style="red", stderr=True)
            sys.exit(1)
        rec = choose_best_account(evaluate_records(entries))
        console.print(f"Automatically recommended from Cloud: [cyan]{rec.selected.email}[/]")
        email = rec.selected.email
        args.email = email

    if not email:
        console.print(
            "[bold red]Error:[/] --email or --from-archive is required for cloud restore/use.",
            style="red",
            stderr=True,
        )
        sys.exit(1)

    entries = list_cloud_backups(cp, email=email, latest_per_email=True)
    if not entries:
        console.print(
            f"[bold red]Error:[/] No backups found in Cloud for {email}.",
            style="red",
            stderr=True,
        )
        sys.exit(1)

    selected = entries[0]
    archive_name = selected.archive_path.name
    metadata_name = archive_name.replace(".tar.gz", ".metadata.json")

    temp_dir = Path(tempfile.mkdtemp(prefix=f"codex-manager-cloud-{args.command}-"))
    archive_path = temp_dir / archive_name
    metadata_path = temp_dir / metadata_name

    console.print(f"Downloading from Cloud: {archive_name} ...")
    cp.download_file(archive_name, archive_path)
    cp.download_file(metadata_name, metadata_path)

    args.from_archive = str(archive_path)
    args.email = None


def build_live_status(args: Any) -> CooldownStatus | None:
    if not getattr(args, "live", False):
        return None

    status_text = read_status_text_from_args(args)
    live_status = parse_live_status_text(
        status_text,
        reference_year=getattr(args, "reference_year", None),
    )

    now = datetime.now().astimezone()
    remaining_seconds = int((live_status.reset_at - now).total_seconds())
    status = "ready" if remaining_seconds <= 0 else "cooldown"

    return CooldownStatus(
        email=live_status.email,
        status=status,
        session_start_at=live_status.session_start_at,
        next_available_at=live_status.reset_at,
        quota_end_detected_at=now,
        validation_status="live",
        proposed_archive_name=live_status.proposed_archive_name,
        remaining_seconds=max(0, remaining_seconds),
        quota_text=live_status.quota_text,
        quota_percent_left=live_status.quota_percent_left,
        is_expired=live_status.is_expired,
    )


def handle_cooldown(args: Any) -> None:
    live_status = build_live_status(args)
    statuses = evaluate_records(list_entries_from_args(args), live_status=live_status)[: args.limit]
    print_statuses_table(statuses, live_email=live_status.email if live_status else None)


def handle_recommend(args: Any) -> None:
    recommendation = choose_best_account(
        evaluate_records(
            list_entries_from_args(args),
            live_status=build_live_status(args),
        )
    )

    from .recommend import format_remaining
    from .ui import Panel

    selected = recommendation.selected
    content = (
        f"[bold cyan]Account:[/] {selected.email}\n"
        f"[bold cyan]Status:[/] {'[bold green]' if selected.status == 'ready' else '[bold yellow]'}{selected.status.upper()}[/]\n"
        f"[bold cyan]Available In:[/] {format_remaining(selected.remaining_seconds)}\n"
        f"[bold cyan]Next Available:[/] {selected.next_available_at.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        f"[bold cyan]Validation:[/] {selected.validation_status}\n\n"
        f"[italic bright_white]{recommendation.reason}[/]"
    )
    console.print(
        Panel(
            content,
            title="[bold bright_magenta]Recommendation[/]",
            border_style="bright_magenta",
            expand=False,
        )
    )


def _read_status_command_input(args: Any) -> str:
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    if args.status_command:
        return read_status_text_from_args(args)
    return capture_tmux_status_text(
        session_name=args.tmux_session_name,
        codex_command=args.codex_command,
        cols=args.tmux_cols,
        rows=args.tmux_rows,
        startup_timeout_seconds=args.startup_timeout_seconds,
        status_timeout_seconds=args.status_timeout_seconds,
    )


def handle_status(args: Any) -> None:
    from .status import TokenExpiredError
    try:
        input_text = _read_status_command_input(args)
    except TokenExpiredError as exc:
        console.print(f"[bold red]Error:[/] {exc}")
        
        # Identification Fallback: Try to identify account to mark it as expired
        current_email = None
        try:
            # Try parsing the partial capture first
            status = parse_live_status_text(exc.output)
            current_email = status.email
        except Exception:
            # If that fails, read from auth.json
            codex_home = Path(getattr(args, "source_dir", None) or "~/.codex").expanduser()
            auth_path = codex_home / "auth.json"
            if auth_path.exists():
                try:
                    auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
                    current_email = auth_data.get("email")
                except Exception:
                    pass
        
        if current_email:
            try:
                patch_metadata(
                    email=current_email,
                    reset_at=None,
                    quota_text="TOKEN EXPIRED: Re-login required.",
                    quota_percent_left=None,
                    args=args,
                    session_start_at=None,
                    is_expired=True,
                    dry_run=getattr(args, "dry_run", False),
                )
            except Exception as patch_exc:
                console.print(f"[yellow]Warning:[/] Failed to patch metadata: {patch_exc}")
        sys.exit(1)

    status = parse_live_status_text(
        input_text,
        reference_year=args.reference_year,
    )
    try:
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
    except Exception as exc:
        console.print(f"[yellow]Warning:[/] Failed to patch metadata: {exc}")
    console.print(live_status_to_text(status))


def handle_backup(args: Any) -> None:
    try:
        archive_path, metadata_path, metadata = perform_backup(args)
    except FileExistsError as exc:
        console.print(f"[bold red]Stop:[/] {exc}")
        console.print(f"[dim]Note: Backups are named after the account's weekly reset time.[/]")
        console.print(f"[dim]If you want to update your current snapshot, run with: [bold white]--force[/][/]")
        sys.exit(1)

    if getattr(args, "cloud", False):
        cp = get_cloud_provider(args)
        if cp:
            if not args.dry_run:
                console.print(f"Uploading to Cloud: {archive_path.name} ...")
                cp.upload_file(archive_path, archive_path.name)
                cp.upload_file(metadata_path, metadata_path.name)
                sync_registry_with_cloud(cp)
                console.print("[green]Cloud upload complete.[/]")
            else:
                console.print(f"Would upload to Cloud: {archive_path.name} ...")
                sync_registry_with_cloud(cp, dry_run=args.dry_run)
        else:
            console.print(
                "[bold red]Error:[/] Could not resolve Cloud (B2) credentials for upload.",
                style="red",
                stderr=True,
            )

    console.print(
        backup_result_to_text(
            archive_path,
            metadata_path,
            metadata,
            dry_run=args.dry_run,
        )
    )


def handle_restore(args: Any) -> None:
    sync_current_account_status(args)
    _ensure_cloud_archive(args)
    archive_path, dest_dir, metadata, existing_backup_path = perform_restore(args)
    console.print(
        restore_result_to_text(
            archive_path,
            dest_dir,
            metadata,
            existing_backup_path,
            dry_run=args.dry_run,
        )
    )


def handle_list_backups(args: Any) -> None:
    entries = list_entries_from_args(args)
    if args.json:
        console.print(json.dumps([asdict(entry) for entry in entries], indent=2, default=str), markup=False)
        return
    print_entries_table(entries)


def handle_prune_backups(args: Any) -> None:
    perform_prune_backups(
        Path(args.backup_dir).expanduser(),
        keep=args.keep,
        keep_latest_per_email=args.keep_latest_per_email,
        dry_run=args.dry_run,
    )


def handle_doctor(args: Any) -> None:
    try:
        run_doctor(
            codex_home=Path(args.source_dir).expanduser(),
            backup_dir=Path(args.backup_dir).expanduser(),
        )
    except SystemExit as exc:
        sys.exit(exc.code)


def handle_profile(args: Any) -> None:
    if args.action == "export":
        export_profile(Path(args.file).expanduser(), dry_run=getattr(args, "dry_run", False))
        if not getattr(args, "dry_run", False):
            console.print(f"Profile exported to {args.file}")
    elif args.action == "import":
        import_profile(Path(args.file).expanduser(), dry_run=getattr(args, "dry_run", False))
        if not getattr(args, "dry_run", False):
            console.print(f"Profile imported from {args.file}")


def handle_prune(args: Any) -> None:
    source_dir = Path(args.source_dir).expanduser()
    plan = perform_prune(args)
    console.print(prune_result_to_text(plan, dry_run=args.dry_run, source_dir=source_dir))


def handle_purge(args: Any) -> None:
    source_dir = Path(args.source_dir).expanduser()
    success = perform_purge(args)
    console.print(purge_result_to_text(success, source_dir=source_dir, dry_run=args.dry_run))


def handle_remove(args: Any) -> None:
    results = perform_remove(args)
    console.print(remove_result_to_text(results, email=args.email, dry_run=args.dry_run))


def handle_use(args: Any) -> None:
    sync_current_account_status(args)
    _ensure_cloud_archive(args)
    archive_path, dest_dir, metadata, existing_backup_path, pruned = perform_use(args)
    console.print(
        use_result_to_text(
            archive_path,
            dest_dir,
            metadata,
            existing_backup_path,
            dry_run=args.dry_run,
            pruned=pruned,
        )
    )


def handle_sync(args: Any) -> None:
    backup_dir = Path(args.backup_dir).expanduser()
    if args.direction == "push":
        push_backup(
            backup_dir=backup_dir,
            bucket_name=args.bucket_name,
            endpoint_url=args.endpoint_url,
            access_key=args.access_key,
            secret_key=args.secret_key,
            dry_run=args.dry_run,
        )
    elif args.direction == "pull":
        pull_backup(
            backup_dir=backup_dir,
            bucket_name=args.bucket_name,
            endpoint_url=args.endpoint_url,
            access_key=args.access_key,
            secret_key=args.secret_key,
            dry_run=args.dry_run,
        )


def main() -> None:
    from .config import load_config

    load_config()

    parser = get_parser()
    args = parser.parse_args()
    handlers = {
        "backup": handle_backup,
        "cooldown": handle_cooldown,
        "doctor": handle_doctor,
        "list-backups": handle_list_backups,
        "profile": handle_profile,
        "prune": handle_prune,
        "purge": handle_purge,
        "remove": handle_remove,
        "prune-backups": handle_prune_backups,
        "recommend": handle_recommend,
        "restore": handle_restore,
        "status": handle_status,
        "sync": handle_sync,
        "use": handle_use,
    }
    handler = handlers.get(args.command)
    if handler is not None:
        handler(args)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
