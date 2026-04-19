from __future__ import annotations

from pathlib import Path
import sys

from .args import get_parser
from .backup import backup_result_to_text, perform_backup
from .cooldown import CooldownStatus, evaluate_records, statuses_to_table
from .doctor import run_doctor
from .inventory import load_inventory, write_inventory
from .list_backups import entries_to_table, list_backups
from .normalize import normalize_directory, records_to_json
from .profile import export_profile, import_profile
from .prune import perform_prune, prune_result_to_text
from .prune_backups import perform_prune_backups
from .recommend import choose_best_account, recommendation_to_text
from .restore import perform_restore, restore_result_to_text
from .status import live_status_to_text, parse_live_status_text
from .sync import pull_backup, push_backup
from .use_account import perform_use, use_result_to_text


def main() -> None:
    from .config import load_config
    load_config()

    parser = get_parser()
    args = parser.parse_args()

    if args.command == "normalize":
        records = normalize_directory(
            Path(args.source_dir),
            session_duration_hours=args.session_duration_hours,
            reference_year=args.reference_year,
        )
        if args.write_inventory:
            write_inventory(records, Path(args.inventory_path))
        print(records_to_json(records))
        return

    if args.command == "cooldown":
        inventory_path = Path(args.inventory_path)
        if args.refresh or not inventory_path.exists():
            records = normalize_directory(
                Path(args.source_dir),
                session_duration_hours=args.session_duration_hours,
                reference_year=args.reference_year,
            )
            write_inventory(records, inventory_path)
        else:
            records = load_inventory(inventory_path)

        live_status = None
        if args.live:
            from .backup import read_status_text_from_args
            from datetime import datetime
            status_text = read_status_text_from_args(args)
            ls = parse_live_status_text(status_text)

            now = datetime.now().astimezone()
            remaining_seconds = int((ls.reset_at - now).total_seconds())
            s = "ready" if remaining_seconds <= 0 else "cooldown"

            live_status = CooldownStatus(
                email=ls.email,
                status=s,
                session_start_at=ls.session_start_at,
                next_available_at=ls.reset_at,
                quota_end_detected_at=now,
                validation_status="live",
                proposed_archive_name=ls.proposed_archive_name,
                remaining_seconds=max(0, remaining_seconds),
            )

        statuses = evaluate_records(records, live_status=live_status)[: args.limit]
        print(statuses_to_table(statuses, live_email=live_status.email if live_status else None))
        return

    if args.command == "recommend":
        inventory_path = Path(args.inventory_path)
        if args.refresh or not inventory_path.exists():
            records = normalize_directory(
                Path(args.source_dir),
                session_duration_hours=args.session_duration_hours,
                reference_year=args.reference_year,
            )
            write_inventory(records, inventory_path)
        else:
            records = load_inventory(inventory_path)

        recommendation = choose_best_account(evaluate_records(records))
        print(recommendation_to_text(recommendation))
        return

    if args.command == "status-parse":
        if args.input_file:
            text = Path(args.input_file).read_text(encoding="utf-8")
        else:
            text = sys.stdin.read()
        status = parse_live_status_text(text, reference_year=args.reference_year)
        print(live_status_to_text(status))
        return

    if args.command == "backup":
        archive_path, metadata_path, metadata = perform_backup(args)
        print(
            backup_result_to_text(
                archive_path,
                metadata_path,
                metadata,
                dry_run=args.dry_run,
            )
        )
        return

    if args.command == "restore":
        archive_path, dest_dir, metadata, existing_backup_path = perform_restore(args)
        print(
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
        entries = list_backups(
            Path(args.backup_dir).expanduser(),
            email=args.email,
            latest_per_email=args.latest_per_email,
            ready=args.ready,
            sort_by=args.sort,
        )
        if args.json:
            import json
            from dataclasses import asdict
            print(json.dumps([asdict(e) for e in entries], indent=2, default=str))
        else:
            print(entries_to_table(entries))
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
            print(f"Profile exported to {args.file}")
        elif args.action == "import":
            import_profile(Path(args.file).expanduser())
            print(f"Profile imported from {args.file}")
        return

    if args.command == "prune":
        source_dir = Path(args.source_dir).expanduser()
        plan = perform_prune(args)
        print(prune_result_to_text(plan, dry_run=args.dry_run, source_dir=source_dir))
        return

    if args.command == "use":
        archive_path, dest_dir, metadata, existing_backup_path, pruned = perform_use(args)
        print(
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
