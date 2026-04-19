from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_BACKUP_DIR
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


def list_backups(
    backup_dir: Path,
    *,
    email: str | None = None,
) -> list[BackupEntry]:
    entries = [build_backup_entry(path) for path in iter_backup_archives(backup_dir)]
    if email is not None:
        entries = [entry for entry in entries if entry.email == email]
    return entries


def entries_to_table(entries: list[BackupEntry]) -> str:
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
                entry.archive_path.name,
                entry.email,
                entry.session_start_at,
                entry.reset_at,
                quota,
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(values: list[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    lines = [format_row(headers), format_row(["-" * width for width in widths])]
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)
