from __future__ import annotations

from pathlib import Path
import sys

from .args import get_parser
from .backup import backup_result_to_text, perform_backup
from .cooldown import evaluate_records, statuses_to_table
from .inventory import load_inventory, write_inventory
from .list_backups import entries_to_table, list_backups
from .normalize import normalize_directory, records_to_json
from .prune import perform_prune, prune_result_to_text
from .recommend import choose_best_account, recommendation_to_text
from .restore import perform_restore, restore_result_to_text
from .status import live_status_to_text, parse_live_status_text
from .use_account import perform_use, use_result_to_text


def main() -> None:
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

        statuses = evaluate_records(records)[: args.limit]
        print(statuses_to_table(statuses))
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
        entries = list_backups(Path(args.backup_dir).expanduser(), email=args.email)
        print(entries_to_table(entries))
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

    parser.print_help()


if __name__ == "__main__":
    main()
