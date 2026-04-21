from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .cloud import B2Provider
from .restore import load_metadata_for_archive


@dataclass(frozen=True)
class BackupEntry:
    archive_path: Path
    email: str
    session_start_at: str
    reset_at: str
    created_at: str
    quota_percent_left: int | None
    quota_text: str


def iter_backup_archives(backup_dir: Path) -> list[Path]:
    if not backup_dir.exists():
        raise FileNotFoundError(f"Backup directory does not exist: {backup_dir}")
    return sorted(
        [
            path
            for path in backup_dir.glob("*-codex.tar.gz")
            if "-latest-codex.tar.gz" not in path.name
        ],
        key=lambda path: path.name,
        reverse=True,
    )


def build_backup_entry(archive_path: Path) -> BackupEntry:
    metadata = load_metadata_for_archive(archive_path)
    return BackupEntry(
        archive_path=archive_path,
        email=metadata.get("email", "unknown"),
        session_start_at=metadata.get("session_start_at", "unknown"),
        reset_at=metadata.get("reset_at", "unknown"),
        created_at=metadata.get("created_at", "unknown"),
        quota_percent_left=metadata.get("quota_percent_left"),
        quota_text=metadata.get("quota_text", "unknown"),
    )

def list_cloud_backups(
    cloud: B2Provider,
    *,
    email: str | None = None,
    latest_per_email: bool = False,
    ready: bool = False,
    sort_by: str = "created_at",
) -> list[BackupEntry]:
    cloud_files = cloud.list_files()
    metadata_files = [f for f in cloud_files if f.name.endswith(".metadata.json")]
    
    entries = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for mf in metadata_files:
            local_mf = tmp_path / mf.name
            try:
                cloud.download_file(mf.name, local_mf)
                metadata = json.loads(local_mf.read_text())
                entries.append(BackupEntry(
                    archive_path=Path(metadata.get("archive_name", mf.name.replace(".metadata.json", ".tar.gz"))),
                    email=metadata.get("email", "unknown"),
                    session_start_at=metadata.get("session_start_at", "unknown"),
                    reset_at=metadata.get("reset_at", "unknown"),
                    created_at=metadata.get("created_at", "unknown"),
                    quota_percent_left=metadata.get("quota_percent_left"),
                    quota_text=metadata.get("quota_text", "unknown"),
                ))
            except Exception:
                continue

    if email is not None:
        entries = [entry for entry in entries if entry.email == email]

    if ready:
        from datetime import datetime
        now = datetime.now().astimezone()
        def is_ready(entry: BackupEntry) -> bool:
            if entry.reset_at == "unknown":
                return False
            try:
                reset_time = datetime.fromisoformat(entry.reset_at)
                return reset_time <= now
            except ValueError:
                return False
        entries = [e for e in entries if is_ready(e)]

    if sort_by == "reset_at":
        entries.sort(key=lambda e: e.reset_at, reverse=True)
    elif sort_by == "session_start_at":
        entries.sort(key=lambda e: e.session_start_at, reverse=True)
    else:
        entries.sort(key=lambda e: e.created_at, reverse=True)

    if latest_per_email:
        seen = set()
        filtered = []
        for e in entries:
            if e.email not in seen:
                seen.add(e.email)
                filtered.append(e)
        entries = filtered

    return entries


def list_backups(
    backup_dir: Path,
    *,
    email: str | None = None,
    latest_per_email: bool = False,
    ready: bool = False,
    sort_by: str = "created_at",
) -> list[BackupEntry]:
    entries = [build_backup_entry(path) for path in iter_backup_archives(backup_dir)]
    if email is not None:
        entries = [entry for entry in entries if entry.email == email]

    if ready:
        from datetime import datetime

        import codex_manager.list_backups  # For mocking
        now = getattr(codex_manager.list_backups, "datetime", datetime).now().astimezone()
        def is_ready(entry: BackupEntry) -> bool:
            if entry.reset_at == "unknown":
                return False
            try:
                dt = getattr(codex_manager.list_backups, "datetime", datetime)
                reset_time = dt.fromisoformat(entry.reset_at)
                return reset_time <= now
            except ValueError:
                return False
        entries = [e for e in entries if is_ready(e)]

    if sort_by == "reset_at":
        entries.sort(key=lambda e: e.reset_at, reverse=True)
    elif sort_by == "session_start_at":
        entries.sort(key=lambda e: e.session_start_at, reverse=True)
    else:
        entries.sort(key=lambda e: e.created_at, reverse=True)

    if latest_per_email:
        seen = set()
        filtered = []
        for e in entries:
            if e.email not in seen:
                seen.add(e.email)
                filtered.append(e)
        entries = filtered

    return entries


def print_entries_table(entries: list[BackupEntry]) -> None:
    from .ui import Panel, Table, console

    table = Table(show_header=True, header_style="bold bright_magenta")
    table.add_column("Archive", style="bright_cyan")
    table.add_column("Email", style="bright_green")
    table.add_column("Session Start", justify="right", style="dim")
    table.add_column("Reset At", justify="right", style="dim")
    table.add_column("Quota", justify="right", style="bright_yellow")

    for entry in entries:
        quota = (
            f"{entry.quota_percent_left}%"
            if entry.quota_percent_left is not None
            else "unknown"
        )
        archive_name = entry.archive_path.name if hasattr(entry, "archive_path") else getattr(entry, "proposed_archive_name", getattr(entry, "archive_name", "unknown"))
        table.add_row(
            archive_name,
            entry.email,
            str(entry.session_start_at),
            str(entry.reset_at),
            quota,
        )

    console.print(Panel(table, title="[bold bright_cyan]Available Backups[/]", border_style="bright_cyan", expand=False))


def entries_to_table(entries: list[BackupEntry]) -> str:
    # For backward compatibility, generate table and render to string for tests.
    headers = [
        "Archive",
        "Email",
        "Session Start",
        "Reset At",
        "Quota",
    ]
    rows = []
    for entry in entries:
        quota = (
            f"{entry.quota_percent_left}%"
            if entry.quota_percent_left is not None
            else "unknown"
        )
        rows.append(
            [
                entry.archive_path.name if hasattr(entry, "archive_path") else getattr(entry, "proposed_archive_name", getattr(entry, "archive_name", "unknown")),
                entry.email,
                entry.session_start_at,
                entry.reset_at,
                quota,
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def format_row(values: list[str]) -> str:
        return "  ".join(str(value).ljust(widths[index]) for index, value in enumerate(values))

    lines = [format_row(headers), format_row(["-" * width for width in widths])]
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)
