from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

from .args import get_parser
from .backup import backup_result_to_text, perform_backup
from .rich_utils import console, error_console
from .cloud import get_cloud_provider
from .cooldown import CooldownStatus, evaluate_records, statuses_to_table
from .doctor import run_doctor
from .list_backups import BackupEntry, entries_to_table, list_backups, list_cloud_backups
from .profile import export_profile, import_profile
from .prune import perform_prune, prune_result_to_text
from .prune_backups import perform_prune_backups
from .recommend import choose_best_account, recommendation_to_text
from .restore import perform_restore, restore_result_to_text
from .status import capture_tmux_status_text, live_status_to_text, parse_live_status_text
from .sync import pull_backup, push_backup
from .use_account import perform_use, use_result_to_text


def list_entries_from_args(args) -> list[BackupEntry]:
    if getattr(args, "cloud", False):
        cp = get_cloud_provider(args)
        if not cp:
            error_console.print("[danger]Error: Could not resolve Cloud (B2) credentials.[/]")
            sys.exit(1)
        return list_cloud_backups(
            cp,
            email=getattr(args, "email", None),
            latest_per_email=getattr(args, "latest_per_email", False),
            ready=getattr(args, "ready", False),
            sort_by=getattr(args, "sort", "created_at"),
        )
    else:
        return list_backups(
            Path(args.backup_dir).expanduser(),
            email=getattr(args, "email", None),
            latest_per_email=getattr(args, "latest_per_email", False),
            ready=getattr(args, "ready", False),
            sort_by=getattr(args, "sort", "created_at"),
        )

def _ensure_cloud_archive(args: Any) -> None:
    """Helper to download archive from cloud if --cloud is set and needed."""
    if not getattr(args, "cloud", False) or getattr(args, "from_archive", None):
        return

    cp = get_cloud_provider(args)
    if not cp:
        error_console.print("[danger]Error: Could not resolve Cloud (B2) credentials.[/]")
        sys.exit(1)
    
    # Resolve email - if not provided, we might need to recommend first
    email = getattr(args, "email", None)
    if not email and args.command == "use":
        # For 'use', we can recommend here
        entries = list_cloud_backups(cp, latest_per_email=True)
        if not entries:
            error_console.print("[danger]Error: No backups found in Cloud.[/]")
            sys.exit(1)
        rec = choose_best_account(evaluate_records(entries))
        from .rich_utils import console
        console.print(f"Automatically recommended from Cloud: {rec.selected.email}")
        email = rec.selected.email
        args.email = email
    
    if not email:
        error_console.print("[danger]Error: --email or --from-archive is required for cloud restore/use.[/]")
        sys.exit(1)

    entries = list_cloud_backups(cp, email=email, latest_per_email=True)
    if not entries:
        error_console.print(f"[danger]Error: No backups found in Cloud for {email}.[/]")
        sys.exit(1)
    
    selected = entries[0]
    archive_name = selected.archive_path.name
    metadata_name = archive_name.replace(".tar.gz", ".metadata.json")
    
    temp_dir = Path(tempfile.mkdtemp(prefix=f"codex-manager-cloud-{args.command}-"))
    archive_path = temp_dir / archive_name
    metadata_path = temp_dir / metadata_name
    
    from .rich_utils import console
    with console.status(f"Downloading from Cloud: {archive_name} ..."):
        cp.download_file(archive_name, archive_path)
        cp.download_file(metadata_name, metadata_path)
    
    args.from_archive = str(archive_path)
    # Clear email to prevent restore from trying to find local latest symlink
    args.email = None

def main() -> None:
    from .config import load_config
    load_config()

    parser = get_parser()
    args = parser.parse_args()

    def build_live_status(args) -> CooldownStatus | None:
        if not getattr(args, "live", False):
            return None

        from datetime import datetime

        from .backup import read_status_text_from_args

        status_text = read_status_text_from_args(args)
        ls = parse_live_status_text(status_text, reference_year=getattr(args, "reference_year", None))

        now = datetime.now().astimezone()
        remaining_seconds = int((ls.reset_at - now).total_seconds())
        status = "ready" if remaining_seconds <= 0 else "cooldown"

        return CooldownStatus(
            email=ls.email,
            status=status,
            session_start_at=ls.session_start_at,
            next_available_at=ls.reset_at,
            quota_end_detected_at=now,
            validation_status="live",
            proposed_archive_name=ls.proposed_archive_name,
            remaining_seconds=max(0, remaining_seconds),
        )

    if args.command == "cooldown":
        entries = list_entries_from_args(args)
        live_status = build_live_status(args)
        statuses = evaluate_records(entries, live_status=live_status)[: args.limit]
        console.print(statuses_to_table(statuses, live_email=live_status.email if live_status else None))
        return

    if args.command == "recommend":
        entries = list_entries_from_args(args)
        recommendation = choose_best_account(evaluate_records(entries, live_status=build_live_status(args)))
        console.print(recommendation_to_text(recommendation))
        return

    if args.command == "status":
        if args.input_file:
            text = Path(args.input_file).read_text(encoding="utf-8")
        elif args.status_command:
            import subprocess

            result = subprocess.run(
                args.status_command,
                shell=True,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Status command failed with exit code {result.returncode}:\n{result.stderr}"
                )
            text = result.stdout
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            text = capture_tmux_status_text(
                session_name=args.tmux_session_name,
                codex_command=args.codex_command,
                cols=args.tmux_cols,
                rows=args.tmux_rows,
                startup_timeout_seconds=args.startup_timeout_seconds,
                status_timeout_seconds=args.status_timeout_seconds,
            )
        status = parse_live_status_text(text, reference_year=args.reference_year)
        console.print(live_status_to_text(status))
        return

    if args.command == "backup":
        archive_path, metadata_path, metadata = perform_backup(args)
        
        if getattr(args, "cloud", False) and not args.dry_run:
            cp = get_cloud_provider(args)
            if cp:
                with console.status(f"Uploading to Cloud: {archive_path.name} ..."):
                    cp.upload_file(archive_path, archive_path.name)
                    cp.upload_file(metadata_path, metadata_path.name)
                console.print("[success]Cloud upload complete.[/]")
            else:
                error_console.print("[danger]Error: Could not resolve Cloud (B2) credentials for upload.[/]")

        console.print(
            backup_result_to_text(
                archive_path,
                metadata_path,
                metadata,
                dry_run=args.dry_run,
            )
        )
        return

    if args.command == "restore":
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
        return

    if args.command == "list-backups":
        entries = list_entries_from_args(args)
        if args.json:
            import json
            from dataclasses import asdict
            print(json.dumps([asdict(e) for e in entries], indent=2, default=str))
        else:
            console.print(entries_to_table(entries))
        return

    if args.command == "prune-backups":
        perform_prune_backups(
            Path(args.backup_dir).expanduser(),
            keep=args.keep,
            keep_latest_per_email=args.keep_latest_per_email,
            dry_run=args.dry_run,
        )
        return

    if args.command == "doctor":
        try:
            run_doctor(
                codex_home=Path(args.source_dir).expanduser(),
                backup_dir=Path(args.backup_dir).expanduser(),
            )
        except SystemExit as e:
            sys.exit(e.code)
        return

    if args.command == "profile":
        if args.action == "export":
            export_profile(Path(args.file).expanduser())
            console.print(f"[success]Profile exported to {args.file}[/]")
        elif args.action == "import":
            import_profile(Path(args.file).expanduser())
            console.print(f"[success]Profile imported from {args.file}[/]")
        return

    if args.command == "prune":
        source_dir = Path(args.source_dir).expanduser()
        plan = perform_prune(args)
        console.print(prune_result_to_text(plan, dry_run=args.dry_run, source_dir=source_dir))
        return

    if args.command == "use":
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
        return

    if args.command == "sync":
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
        return

    parser.print_help()


if __name__ == "__main__":
    main()
