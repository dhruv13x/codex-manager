from __future__ import annotations

import argparse
import sys
from . import __version__

from .config import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_CODEX_HOME,
    DEFAULT_COOLDOWN_DISPLAY_LIMIT,
    load_config,
)
from .ui import Panel, Table, console


class RichHelpParser(argparse.ArgumentParser):
    """Custom parser that overrides print_help to display a Rich-based help screen."""

    def error(self, message):
        console.print(f"[bold red]Error:[/ ] {message}", stderr=True)
        console.print("[dim]Use --help for usage information.[/]", stderr=True)
        sys.exit(2)

    def print_help(self, file=None):
        # Header
        console.print(Panel("[bold bright_cyan]Codex Manager[/]\n[italic bright_green]Account snapshot and quota manager for OpenAI Codex[/]", expand=False, border_style="bright_cyan"))
        
        console.print(f"\n[bold bright_white]Usage:[/ ] [dim]{self.format_usage().strip().replace('usage: ', '')}[/]")

        if self.description:
            console.print(f"\n[italic bright_white]{self.description}[/]")

        # Subcommands or Arguments
        # We can detect if we have subparsers
        subparsers_actions = [
            action for action in self._actions 
            if isinstance(action, argparse._SubParsersAction)
        ]
        
        if subparsers_actions:
            console.print("\n[bold bright_magenta]Available Commands:[/ ]")
            table = Table(show_header=False, box=None, padding=(0, 2))
            for action in subparsers_actions:
                # _SubParsersAction stores choices in a dict where values are the parsers
                for choice, subparser in action.choices.items():
                    # The help for the choice is stored in the subparser's description or a special attribute
                    help_text = getattr(subparser, 'help', '')
                    if not help_text:
                        # Search for the action that created this choice
                        for sp_action in action._choices_actions:
                            if sp_action.dest == choice:
                                help_text = sp_action.help
                                break
                    table.add_row(f"[bold bright_green]{choice}[/]", f"[dim]{help_text}[/]")
            console.print(table)
        
        # Regular arguments
        action_groups = [
            group for group in self._action_groups 
            if group.title != 'positional arguments' or not subparsers_actions
        ]

        for group in action_groups:
            if not group._group_actions:
                continue
            
            # Skip empty or boring groups
            if group.title == "options" and len(group._group_actions) <= 1: # just help
                continue

            console.print(f"\n[bold bright_yellow]{group.title.capitalize()}:[/ ]")
            table = Table(show_header=False, box=None, padding=(0, 2))
            for action in group._group_actions:
                opts = ", ".join(action.option_strings) if action.option_strings else action.dest
                help_text = action.help if action.help else ""
                # Replace default values in help text for better look
                if action.default and action.default != argparse.SUPPRESS and "[default:" not in help_text:
                    # Only add if it's a simple type
                    if isinstance(action.default, (str, int, float, bool)):
                         help_text += f" [dim](default: {action.default})[/]"

                table.add_row(f"[bold bright_cyan]{opts}[/]", f"[white]{help_text}[/]")
            console.print(table)

        console.print("\n[dim]Run 'cm <command> --help' for more information on a specific command.[/]")

def get_parser() -> argparse.ArgumentParser:
    config = load_config()

    def _get_default(key: str, fallback: str | int | float | bool | None) -> str | int | float | bool | None:
        return config.get(key, fallback)

    parser = RichHelpParser(prog="codex-manager", description="Manage your Codex account snapshots and quotas.")
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    cooldown_parser = subparsers.add_parser(
        "cooldown",
        help="Show weekly availability from backup metadata, optionally merged with live Codex status.",
    )
    cooldown_parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing backup archives and metadata.",
    )
    cooldown_parser.add_argument(
        "--live",
        action="store_true",
        help="Query current live account via /status and merge with stored backups.",
    )
    cooldown_parser.add_argument(
        "--status-command",
        help="Shell command that prints parseable Codex status text for --live mode.",
    )
    cooldown_parser.add_argument(
        "--codex-command",
        default="codex --no-alt-screen",
        help="Command used to launch Codex for live tmux capture in --live mode.",
    )
    cooldown_parser.add_argument(
        "--tmux-session-name",
        default=None,
        help="Temporary tmux session name used for live status capture in --live mode.",
    )
    cooldown_parser.add_argument(
        "--tmux-cols",
        type=int,
        default=120,
        help="tmux capture width for live status capture in --live mode.",
    )
    cooldown_parser.add_argument(
        "--tmux-rows",
        type=int,
        default=40,
        help="tmux capture height for live status capture in --live mode.",
    )
    cooldown_parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the Codex prompt in --live mode.",
    )
    cooldown_parser.add_argument(
        "--status-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the status panel in --live mode.",
    )
    cooldown_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_COOLDOWN_DISPLAY_LIMIT,
        help="Maximum number of accounts to display.",
    )
    cooldown_parser.add_argument(
        "--cloud",
        action="store_true",
        help="Query availability from Cloud (B2) metadata.",
    )
    cooldown_parser.add_argument("--bucket", help="B2 Bucket Name")
    cooldown_parser.add_argument("--b2-id", help="B2 Key ID")
    cooldown_parser.add_argument("--b2-key", help="B2 App Key")

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Recommend the best account to use next from backup metadata, optionally merged with live Codex status.",
    )
    recommend_parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing backup archives and metadata.",
    )
    recommend_parser.add_argument(
        "--live",
        action="store_true",
        help="Query current live account via /status and merge with stored backups.",
    )
    recommend_parser.add_argument(
        "--status-command",
        help="Shell command that prints parseable Codex status text for --live mode.",
    )
    recommend_parser.add_argument(
        "--reference-year",
        type=int,
        help="Year used when the status text omits the year in reset time.",
    )
    recommend_parser.add_argument(
        "--codex-command",
        default="codex --no-alt-screen",
        help="Command used to launch Codex for live tmux capture in --live mode.",
    )
    recommend_parser.add_argument(
        "--tmux-session-name",
        default=None,
        help="Temporary tmux session name used for live status capture in --live mode.",
    )
    recommend_parser.add_argument(
        "--tmux-cols",
        type=int,
        default=120,
        help="tmux capture width for live status capture in --live mode.",
    )
    recommend_parser.add_argument(
        "--tmux-rows",
        type=int,
        default=40,
        help="tmux capture height for live status capture in --live mode.",
    )
    recommend_parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the Codex prompt in --live mode.",
    )
    recommend_parser.add_argument(
        "--status-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the status panel in --live mode.",
    )
    recommend_parser.add_argument(
        "--cloud",
        action="store_true",
        help="Recommend from Cloud (B2) metadata.",
    )
    recommend_parser.add_argument(
        "--use",
        action="store_true",
        help="Immediately switch to the recommended account using the same workflow as `cm use`.",
    )
    recommend_parser.add_argument(
        "--dest-dir",
        default=str(_get_default("codex_home", str(DEFAULT_CODEX_HOME))),
        help="Codex home directory to restore into when used with --use.",
    )
    recommend_parser.add_argument(
        "--without-status-check",
        action="store_true",
        help="Skip current account status capture before switching when used with --use.",
    )
    recommend_parser.add_argument(
        "--clean",
        action="store_true",
        help="Prune runtime state and then do a full restore for a clean start when used with --use.",
    )
    recommend_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without switching when used with --use.",
    )
    recommend_parser.add_argument(
        "--force",
        action="store_true",
        help="Reserved for future full-restore switching behavior; auth-only switching does not replace the whole destination.",
    )
    recommend_parser.add_argument("--bucket", help="B2 Bucket Name")
    recommend_parser.add_argument("--b2-id", help="B2 Key ID")
    recommend_parser.add_argument("--b2-key", help="B2 App Key")

    status_parser = subparsers.add_parser(
        "status",
        help="Parse Codex /status text or tmux helper output into exact backup metadata.",
    )
    status_parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing backup archives and metadata.",
    )
    status_parser.add_argument(
        "--input-file",
        help="Read status text from a file instead of stdin.",
    )
    status_parser.add_argument(
        "--status-command",
        help="Shell command that prints parseable Codex status text.",
    )
    status_parser.add_argument(
        "--reference-year",
        type=int,
        help="Year used when the status text omits the year in reset time.",
    )
    status_parser.add_argument(
        "--codex-command",
        default="codex --no-alt-screen",
        help="Command used to launch Codex for live tmux capture.",
    )
    status_parser.add_argument(
        "--tmux-session-name",
        default=None,
        help="Temporary tmux session name used for live status capture.",
    )
    status_parser.add_argument(
        "--tmux-cols",
        type=int,
        default=120,
        help="tmux capture width for live status capture.",
    )
    status_parser.add_argument(
        "--tmux-rows",
        type=int,
        default=40,
        help="tmux capture height for live status capture.",
    )
    status_parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the Codex prompt.",
    )
    status_parser.add_argument(
        "--status-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the status panel.",
    )
    status_parser.add_argument(
        "--cloud",
        action="store_true",
        help="Update status metadata in Cloud (B2) as well.",
    )
    status_parser.add_argument("--bucket", help="B2 Bucket Name")
    status_parser.add_argument("--b2-id", help="B2 Key ID")
    status_parser.add_argument("--b2-key", help="B2 App Key")

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
        default=None,
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
        "--without-status-check",
        action="store_true",
        help="Skip live status capture and use current time minus 7 days for cooldown calculation.",
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
    backup_parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Only backup auth.json, config.toml, installation_id, etc. instead of the full state.",
    )
    backup_parser.add_argument(
        "--prune-first",
        action="store_true",
        help="Run prune on runtime state before taking the backup.",
    )
    backup_parser.add_argument(
        "--cloud",
        action="store_true",
        help="Create local backup AND upload to Cloud (B2).",
    )
    backup_parser.add_argument("--bucket", help="B2 Bucket Name")
    backup_parser.add_argument("--b2-id", help="B2 Key ID")
    backup_parser.add_argument("--b2-key", help="B2 App Key")

    restore_parser = subparsers.add_parser(
        "restore",
        help="Full State Recovery: Restore an entire Codex environment (Auth + History + Logs) from a backup.",
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
        default=str(_get_default("backup_dir", str(DEFAULT_BACKUP_DIR))),
        help="Directory containing backup archives and metadata.",
    )
    restore_parser.add_argument(
        "--dest-dir",
        default=str(_get_default("codex_home", str(DEFAULT_CODEX_HOME))),
        help="Codex home directory to restore into.",
    )
    restore_parser.add_argument(
        "--status-command",
        help="Shell command that prints parseable Codex status text.",
    )
    restore_parser.add_argument(
        "--reference-year",
        type=int,
        help="Year used when the status text omits the year in reset time.",
    )
    restore_parser.add_argument(
        "--codex-command",
        default="codex --no-alt-screen",
        help="Command used to launch Codex for live tmux capture.",
    )
    restore_parser.add_argument(
        "--tmux-session-name",
        default=None,
        help="Temporary tmux session name used for live status capture.",
    )
    restore_parser.add_argument(
        "--tmux-cols",
        type=int,
        default=120,
        help="tmux capture width for live status capture.",
    )
    restore_parser.add_argument(
        "--tmux-rows",
        type=int,
        default=40,
        help="tmux capture height for live status capture.",
    )
    restore_parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the Codex prompt.",
    )
    restore_parser.add_argument(
        "--status-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the status panel.",
    )
    restore_parser.add_argument(
        "--without-status-check",
        action="store_true",
        help="Skip current account status capture before restore.",
    )
    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and stage the restore without changing the destination.",
    )
    restore_parser.add_argument(
        "--force",
        action="store_true",
        help="Delete an existing destination instead of moving it aside to a safety backup.",
    )
    restore_parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Identity Only: Only restore auth.json and config files, preserving current session history/logs.",
    )
    restore_parser.add_argument(
        "--cloud",
        action="store_true",
        help="Restore from Cloud (B2).",
    )
    restore_parser.add_argument("--bucket", help="B2 Bucket Name")
    restore_parser.add_argument("--b2-id", help="B2 Key ID")
    restore_parser.add_argument("--b2-key", help="B2 App Key")

    list_backups_parser = subparsers.add_parser(
        "list-backups",
        help="List available Codex backup archives with metadata.",
    )
    list_backups_parser.add_argument(
        "--backup-dir",
        default=str(_get_default("backup_dir", str(DEFAULT_BACKUP_DIR))),
        help="Directory containing backup archives and metadata.",
    )
    list_backups_parser.add_argument(
        "--email",
        help="Filter backups for a specific email.",
    )
    list_backups_parser.add_argument(
        "--latest-per-email",
        action="store_true",
        default=True,
        help="Only show the latest backup for each email (Default).",
    )
    list_backups_parser.add_argument(
        "--all",
        action="store_false",
        dest="latest_per_email",
        help="Show all backups, including historical and duplicate entries.",
    )
    list_backups_parser.add_argument(
        "--ready",
        action="store_true",
        help="Only show backups whose cooldown has expired.",
    )
    list_backups_parser.add_argument(
        "--sort",
        choices=["reset_at", "session_start_at", "created_at"],
        default="created_at",
        help="Sort backups by the specified field.",
    )
    list_backups_parser.add_argument(
        "--json",
        action="store_true",
        help="Output the list as JSON.",
    )
    list_backups_parser.add_argument(
        "--cloud",
        action="store_true",
        help="List backups from Cloud (B2).",
    )
    list_backups_parser.add_argument("--bucket", help="B2 Bucket Name")
    list_backups_parser.add_argument("--b2-id", help="B2 Key ID")
    list_backups_parser.add_argument("--b2-key", help="B2 App Key")

    prune_backups_parser = subparsers.add_parser(
        "prune-backups",
        help="Delete old backup archives.",
    )
    prune_backups_parser.add_argument(
        "--backup-dir",
        default=str(_get_default("backup_dir", str(DEFAULT_BACKUP_DIR))),
        help="Directory containing backup archives and metadata.",
    )
    prune_backups_parser.add_argument(
        "--keep",
        type=int,
        help="Number of most recent backups to keep.",
    )
    prune_backups_parser.add_argument(
        "--keep-latest-per-email",
        action="store_true",
        help="Keep only the latest backup per email, pruning all older ones.",
    )
    prune_backups_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything.",
    )

    profile_parser = subparsers.add_parser(
        "profile",
        help="Export or import the complete codex manager profile state.",
    )
    profile_parser.add_argument(
        "action",
        choices=["export", "import"],
        help="Action to perform: export or import.",
    )
    profile_parser.add_argument(
        "file",
        help="Path to the profile archive (.tar.gz) to export to or import from.",
    )
    profile_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without modifying metadata.",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Verify dependencies, directories, and status parser.",
    )
    doctor_parser.add_argument(
        "--source-dir",
        default=str(_get_default("codex_home", str(DEFAULT_CODEX_HOME))),
        help="Codex home directory to check.",
    )
    doctor_parser.add_argument(
        "--backup-dir",
        default=str(_get_default("backup_dir", str(DEFAULT_BACKUP_DIR))),
        help="Directory containing backup archives and metadata to check.",
    )

    prune_parser = subparsers.add_parser(
        "prune",
        help="Remove Codex runtime state while preserving auth.json and account identity.",
    )
    prune_parser.add_argument(
        "--source-dir",
        default=str(_get_default("codex_home", str(DEFAULT_CODEX_HOME))),
        help="Codex home directory to prune.",
    )
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything.",
    )

    use_parser = subparsers.add_parser(
        "use",
        help="Quick Switcher: Log into a backed-up account. Defaults to Auth-Only (preserves current history).",
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
        default=str(_get_default("backup_dir", str(DEFAULT_BACKUP_DIR))),
        help="Directory containing backup archives and metadata.",
    )
    use_parser.add_argument(
        "--dest-dir",
        default=str(_get_default("codex_home", str(DEFAULT_CODEX_HOME))),
        help="Codex home directory to restore into.",
    )
    use_parser.add_argument(
        "--status-command",
        help="Shell command that prints parseable Codex status text.",
    )
    use_parser.add_argument(
        "--reference-year",
        type=int,
        help="Year used when the status text omits the year in reset time.",
    )
    use_parser.add_argument(
        "--codex-command",
        default="codex --no-alt-screen",
        help="Command used to launch Codex for live tmux capture.",
    )
    use_parser.add_argument(
        "--tmux-session-name",
        default=None,
        help="Temporary tmux session name used for live status capture.",
    )
    use_parser.add_argument(
        "--tmux-cols",
        type=int,
        default=120,
        help="tmux capture width for live status capture.",
    )
    use_parser.add_argument(
        "--tmux-rows",
        type=int,
        default=40,
        help="tmux capture height for live status capture.",
    )
    use_parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the Codex prompt.",
    )
    use_parser.add_argument(
        "--status-timeout-seconds",
        type=float,
        default=20.0,
        help="Seconds to wait for the status panel.",
    )
    use_parser.add_argument(
        "--without-status-check",
        action="store_true",
        help="Skip current account status capture before switching.",
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
    use_parser.add_argument(
        "--cloud",
        action="store_true",
        help="Use a backup from Cloud (B2).",
    )
    use_parser.add_argument("--bucket", help="B2 Bucket Name")
    use_parser.add_argument("--b2-id", help="B2 Key ID")
    use_parser.add_argument("--b2-key", help="B2 App Key")
    status_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without modifying metadata.",
    )

    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync backups to or from an S3-compatible bucket.",
    )
    sync_parser.add_argument(
        "direction",
        choices=["push", "pull"],
        help="Direction to sync: 'push' to upload, 'pull' to download.",
    )
    sync_parser.add_argument(
        "--bucket-name",
        required=True,
        help="Name of the S3 bucket to sync with.",
    )
    sync_parser.add_argument(
        "--endpoint-url",
        help="S3 endpoint URL (e.g. for Backblaze B2). Defaults to AWS_ENDPOINT_URL env var.",
    )
    sync_parser.add_argument(
        "--access-key",
        help="AWS access key ID. Defaults to AWS_ACCESS_KEY_ID env var.",
    )
    sync_parser.add_argument(
        "--secret-key",
        help="AWS secret access key. Defaults to AWS_SECRET_ACCESS_KEY env var.",
    )
    sync_parser.add_argument(
        "--backup-dir",
        default=str(_get_default("backup_dir", str(DEFAULT_BACKUP_DIR))),
        help="Directory containing backup archives and metadata.",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without actually syncing.",
    )

    purge_parser = subparsers.add_parser(
        "purge",
        help="Total Wipeout: Completely delete the Codex home directory (Auth, Identity, and all State).",
    )
    purge_parser.add_argument(
        "--source-dir",
        default=str(_get_default("codex_home", str(DEFAULT_CODEX_HOME))),
        help="Codex home directory to purge.",
    )
    purge_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything.",
    )
    purge_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Confirm the purge without prompting.",
    )

    remove_parser = subparsers.add_parser(
        "remove",
        help="Account Cleanup: Delete all local (and optionally cloud) backups and registry entries for a specific email.",
    )
    remove_parser.add_argument(
        "--email",
        required=True,
        help="The email address of the account to remove.",
    )
    remove_parser.add_argument(
        "--backup-dir",
        default=str(_get_default("backup_dir", str(DEFAULT_BACKUP_DIR))),
        help="Directory containing backup archives and metadata.",
    )
    remove_parser.add_argument(
        "--cloud",
        action="store_true",
        help="Also remove backups and registry entries from Cloud (B2).",
    )
    remove_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything.",
    )
    remove_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Confirm the removal without prompting.",
    )
    remove_parser.add_argument("--bucket", help="B2 Bucket Name")
    remove_parser.add_argument("--b2-id", help="B2 Key ID")
    remove_parser.add_argument("--b2-key", help="B2 App Key")

    return parser
