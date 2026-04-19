from __future__ import annotations

import argparse
from .config import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_COOLDOWN_DISPLAY_LIMIT,
    DEFAULT_INVENTORY_PATH,
    DEFAULT_CODEX_HOME,
    DEFAULT_REFERENCE_YEAR,
    DEFAULT_SAMPLE_HOME,
    DEFAULT_SESSION_DURATION_HOURS,
)


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-manager")
    subparsers = parser.add_subparsers(dest="command")

    normalize_parser = subparsers.add_parser(
        "normalize",
        help="Normalize legacy Codex auth snapshot names into a machine-readable inventory.",
    )
    normalize_parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SAMPLE_HOME),
        help="Directory containing legacy *_auth.json files.",
    )
    normalize_parser.add_argument(
        "--session-duration-hours",
        type=float,
        default=DEFAULT_SESSION_DURATION_HOURS,
        help="Hours to subtract from auth file mtime to infer session start.",
    )
    normalize_parser.add_argument(
        "--reference-year",
        type=int,
        default=DEFAULT_REFERENCE_YEAR,
        help="Year used when expanding legacy day-month tokens such as 21apr.",
    )
    normalize_parser.add_argument(
        "--write-inventory",
        action="store_true",
        help="Write the normalized inventory to disk.",
    )
    normalize_parser.add_argument(
        "--inventory-path",
        default=str(DEFAULT_INVENTORY_PATH),
        help="Path to write the normalized inventory JSON.",
    )
    normalize_parser.set_defaults(write_inventory=True)

    cooldown_parser = subparsers.add_parser(
        "cooldown",
        help="Show weekly availability from normalized inventory records.",
    )
    cooldown_parser.add_argument(
        "--inventory-path",
        default=str(DEFAULT_INVENTORY_PATH),
        help="Path to the normalized inventory JSON.",
    )
    cooldown_parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SAMPLE_HOME),
        help="Directory containing legacy *_auth.json files when refreshing inventory.",
    )
    cooldown_parser.add_argument(
        "--session-duration-hours",
        type=float,
        default=DEFAULT_SESSION_DURATION_HOURS,
        help="Hours to subtract from auth file mtime to infer session start.",
    )
    cooldown_parser.add_argument(
        "--reference-year",
        type=int,
        default=DEFAULT_REFERENCE_YEAR,
        help="Year used when expanding legacy day-month tokens such as 21apr.",
    )
    cooldown_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Regenerate inventory from source-dir before showing cooldowns.",
    )
    cooldown_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_COOLDOWN_DISPLAY_LIMIT,
        help="Maximum number of accounts to display.",
    )

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Recommend the best account to use next from normalized inventory records.",
    )
    recommend_parser.add_argument(
        "--inventory-path",
        default=str(DEFAULT_INVENTORY_PATH),
        help="Path to the normalized inventory JSON.",
    )
    recommend_parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SAMPLE_HOME),
        help="Directory containing legacy *_auth.json files when refreshing inventory.",
    )
    recommend_parser.add_argument(
        "--session-duration-hours",
        type=float,
        default=DEFAULT_SESSION_DURATION_HOURS,
        help="Hours to subtract from auth file mtime to infer session start.",
    )
    recommend_parser.add_argument(
        "--reference-year",
        type=int,
        default=DEFAULT_REFERENCE_YEAR,
        help="Year used when expanding legacy day-month tokens such as 21apr.",
    )
    recommend_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Regenerate inventory from source-dir before recommending an account.",
    )

    status_parser = subparsers.add_parser(
        "status-parse",
        help="Parse Codex /status text or tmux helper output into exact backup metadata.",
    )
    status_parser.add_argument(
        "--input-file",
        help="Read status text from a file instead of stdin.",
    )
    status_parser.add_argument(
        "--reference-year",
        type=int,
        help="Year used when the status text omits the year in reset time.",
    )

    backup_parser = subparsers.add_parser(
        "backup",
        help="Create a live Codex backup named from exact /status reset time.",
    )
    backup_parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_CODEX_HOME),
        help="Codex home directory to archive.",
    )
    backup_parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory where backup archives and metadata are written.",
    )
    backup_parser.add_argument(
        "--status-file",
        help="Read Codex status text from a file instead of capturing it live.",
    )
    backup_parser.add_argument(
        "--status-command",
        help="Shell command that prints parseable Codex status text.",
    )
    backup_parser.add_argument(
        "--reference-year",
        type=int,
        help="Year used when the status text omits the year in reset time.",
    )
    backup_parser.add_argument(
        "--codex-command",
        default="codex --no-alt-screen",
        help="Command used to launch Codex for live tmux capture.",
    )
    backup_parser.add_argument(
        "--tmux-session-name",
        default="codexmgr_capture",
        help="Temporary tmux session name used for live status capture.",
    )
    backup_parser.add_argument(
        "--tmux-cols",
        type=int,
        default=120,
        help="tmux capture width for live status capture.",
    )
    backup_parser.add_argument(
        "--tmux-rows",
        type=int,
        default=40,
        help="tmux capture height for live status capture.",
    )
    backup_parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the Codex prompt.",
    )
    backup_parser.add_argument(
        "--status-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the status panel.",
    )
    backup_parser.add_argument(
        "--include-tmp",
        action="store_true",
        help="Include tmp and .tmp directories in the archive.",
    )
    backup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute paths and metadata without creating files.",
    )
    backup_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing archive if the computed name already exists.",
    )

    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore a Codex backup archive into a target Codex home directory.",
    )
    restore_parser.add_argument(
        "--from-archive",
        help="Path to a specific Codex backup archive.",
    )
    restore_parser.add_argument(
        "--email",
        help="Restore from the latest symlink for this email.",
    )
    restore_parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing backup archives and metadata.",
    )
    restore_parser.add_argument(
        "--dest-dir",
        default=str(DEFAULT_CODEX_HOME),
        help="Codex home directory to restore into.",
    )
    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and stage the restore without changing the destination.",
    )
    restore_parser.add_argument(
        "--force",
        action="store_true",
        help="Delete an existing destination instead of moving it aside to a timestamped .bak path.",
    )

    list_backups_parser = subparsers.add_parser(
        "list-backups",
        help="List available Codex backup archives with metadata.",
    )
    list_backups_parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing backup archives and metadata.",
    )
    list_backups_parser.add_argument(
        "--email",
        help="Filter backups for a specific email.",
    )

    prune_parser = subparsers.add_parser(
        "prune",
        help="Remove Codex runtime state while preserving auth.json and account identity.",
    )
    prune_parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_CODEX_HOME),
        help="Codex home directory to prune.",
    )
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything.",
    )

    use_parser = subparsers.add_parser(
        "use",
        help="Switch to a backed-up account. Default is auth-only; --clean performs a clean-state restore.",
    )
    use_parser.add_argument(
        "--from-archive",
        help="Path to a specific Codex backup archive.",
    )
    use_parser.add_argument(
        "--email",
        help="Use the latest backup symlink for this email.",
    )
    use_parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing backup archives and metadata.",
    )
    use_parser.add_argument(
        "--dest-dir",
        default=str(DEFAULT_CODEX_HOME),
        help="Codex home directory to restore into.",
    )
    use_parser.add_argument(
        "--clean",
        action="store_true",
        help="Prune runtime state and then do a full restore for a clean start.",
    )
    use_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without modifying the destination.",
    )
    use_parser.add_argument(
        "--force",
        action="store_true",
        help="Reserved for future full-restore switching behavior; auth-only switching does not replace the whole destination.",
    )

    return parser
