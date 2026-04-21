from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .list_backups import BackupEntry


@dataclass(frozen=True)
class CooldownStatus:
    email: str
    status: str
    session_start_at: datetime
    next_available_at: datetime
    quota_end_detected_at: datetime
    validation_status: str
    proposed_archive_name: str
    remaining_seconds: int


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def evaluate_entry(entry: BackupEntry, now: datetime | None = None) -> CooldownStatus:
    current = now.astimezone() if now is not None else datetime.now().astimezone()
    session_start_at = parse_iso_datetime(entry.session_start_at)
    next_available_at = parse_iso_datetime(entry.reset_at)
    quota_end_detected_at = parse_iso_datetime(entry.created_at)
    remaining_seconds = int((next_available_at - current).total_seconds())
    status = "ready" if remaining_seconds <= 0 else "cooldown"

    return CooldownStatus(
        email=entry.email,
        status=status,
        session_start_at=session_start_at,
        next_available_at=next_available_at,
        quota_end_detected_at=quota_end_detected_at,
        validation_status="backup",
        proposed_archive_name=entry.archive_path.name,
        remaining_seconds=max(0, remaining_seconds),
    )


def evaluate_records(
    entries: list[BackupEntry],
    now: datetime | None = None,
    live_status: CooldownStatus | None = None,
) -> list[CooldownStatus]:
    statuses = [evaluate_entry(entry, now=now) for entry in entries]

    if live_status is not None:
        # replace any historical status for the live account
        statuses = [s for s in statuses if s.email != live_status.email]
        statuses.append(live_status)

    return sorted(
        statuses,
        key=lambda item: (
            item.status != "ready",
            item.next_available_at,
            item.email,
        ),
    )


def format_remaining(seconds: int) -> str:
    if seconds <= 0:
        return "now"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def print_statuses_table(statuses: list[CooldownStatus], live_email: str | None = None) -> None:
    from .ui import Panel, Table, console

    table = Table(show_header=True, header_style="bold bright_magenta")
    table.add_column("Account", style="bright_cyan")
    table.add_column("Status", justify="center")
    table.add_column("Available", justify="right", style="bright_yellow")
    table.add_column("Session Start", justify="right", style="dim")
    table.add_column("Reset At", justify="right", style="dim")
    table.add_column("Source", style="dim italic")

    for status in statuses:
        account_display = f"[bold]*{status.email}[/]" if status.email == live_email else status.email
        status_display = f"[bold bright_green]{status.status.upper()}[/]" if status.status == "ready" else f"[bold bright_yellow]{status.status.upper()}[/]"

        table.add_row(
            account_display,
            status_display,
            format_remaining(status.remaining_seconds),
            status.session_start_at.strftime("%Y-%m-%d %H:%M:%S"),
            status.quota_end_detected_at.strftime("%Y-%m-%d %H:%M:%S"),
            status.validation_status,
        )

    console.print(Panel(table, title="[bold bright_cyan]Account Cooldown Status[/]", border_style="bright_cyan", expand=False))


def statuses_to_table(statuses: list[CooldownStatus], live_email: str | None = None) -> str:
    # For backward compatibility, generate table and render to string.
    # However since Table class doesn't necessarily have a render() returning string when rich is used,
    # we can recreate the raw string generator for tests, but actually, tests can be updated or we can just keep the raw generation here.
    headers = [
        "Account",
        "Status",
        "Available",
        "Session Start",
        "Reset At",
        "Source",
    ]
    rows = []
    for status in statuses:
        account_display = f"*{status.email}" if status.email == live_email else status.email
        rows.append(
            [
                account_display,
                status.status.upper(),
                format_remaining(status.remaining_seconds),
                status.session_start_at.strftime("%Y-%m-%d %H:%M:%S"),
                status.quota_end_detected_at.strftime("%Y-%m-%d %H:%M:%S"),
                status.validation_status,
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
