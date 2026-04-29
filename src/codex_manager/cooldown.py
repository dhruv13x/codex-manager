from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

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
    quota_text: str | None = None
    quota_percent_left: int | None = None
    is_expired: bool = False


def parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt


def evaluate_entry(entry: BackupEntry, now: datetime | None = None) -> CooldownStatus:
    current = now.astimezone() if now is not None else datetime.now().astimezone()
    session_start_at = parse_iso_datetime(entry.session_start_at)
    next_available_at = parse_iso_datetime(entry.reset_at)
    quota_end_detected_at = parse_iso_datetime(entry.created_at)
    remaining_seconds = int((next_available_at - current).total_seconds())
    status = "ready" if remaining_seconds <= 0 else "cooldown"

    is_expired = getattr(entry, "is_expired", False)

    return CooldownStatus(
        email=entry.email,
        status=status,
        session_start_at=session_start_at,
        next_available_at=next_available_at,
        quota_end_detected_at=quota_end_detected_at,
        validation_status="backup",
        proposed_archive_name=entry.archive_path.name,
        remaining_seconds=max(0, remaining_seconds),
        quota_text=getattr(entry, "quota_text", None),
        quota_percent_left=getattr(entry, "quota_percent_left", None),
        is_expired=is_expired,
    )


def evaluate_records(
    entries: list[BackupEntry],
    now: datetime | None = None,
    live_status: CooldownStatus | None = None,
) -> list[CooldownStatus]:
    statuses = [evaluate_entry(entry, now=now) for entry in entries]
    
    # Merge with registry
    from .registry import load_registry
    registry_data = load_registry()
    
    current = now.astimezone() if now is not None else datetime.now().astimezone()
    
    for email, reg_entry in registry_data.items():
        if "updated_at" not in reg_entry:
            continue
            
        reg_updated_at = parse_iso_datetime(reg_entry["updated_at"])
        reg_reset_at = reg_entry.get("reset_at")
        reg_is_expired = reg_entry.get("is_expired", False)
        
        # Check if we already have a status for this email from backups
        existing_idx = next((i for i, s in enumerate(statuses) if s.email == email), None)
        
        if existing_idx is not None:
            existing_status = statuses[existing_idx]
            # If registry is newer, update the status
            if reg_updated_at > existing_status.quota_end_detected_at:
                if reg_reset_at is not None:
                    next_available_at = parse_iso_datetime(reg_reset_at)
                    session_start_at = parse_iso_datetime(reg_entry.get("session_start_at", reg_reset_at))
                elif reg_is_expired:
                    next_available_at = existing_status.next_available_at
                    session_start_at = existing_status.session_start_at
                else:
                    continue
                remaining_seconds = int((next_available_at - current).total_seconds())
                statuses[existing_idx] = CooldownStatus(
                    email=email,
                    status="ready" if remaining_seconds <= 0 else "cooldown",
                    session_start_at=session_start_at,
                    next_available_at=next_available_at,
                    quota_end_detected_at=reg_updated_at,
                    validation_status="registry",
                    proposed_archive_name=existing_status.proposed_archive_name,
                    remaining_seconds=max(0, remaining_seconds),
                    quota_text=reg_entry.get("quota_text"),
                    quota_percent_left=reg_entry.get("quota_percent_left"),
                    is_expired=reg_is_expired
                )
        else:
            # Create a new status from registry
            if reg_reset_at is not None:
                next_available_at = parse_iso_datetime(reg_reset_at)
                session_start_at = parse_iso_datetime(reg_entry.get("session_start_at", reg_reset_at))
            elif reg_is_expired:
                next_available_at = reg_updated_at
                session_start_at = reg_updated_at - timedelta(days=7)
            else:
                continue
            remaining_seconds = int((next_available_at - current).total_seconds())
            statuses.append(
                CooldownStatus(
                    email=email,
                    status="ready" if remaining_seconds <= 0 else "cooldown",
                    session_start_at=session_start_at,
                    next_available_at=next_available_at,
                    quota_end_detected_at=reg_updated_at,
                    validation_status="registry",
                    proposed_archive_name="none",
                    remaining_seconds=max(0, remaining_seconds),
                    quota_text=reg_entry.get("quota_text"),
                    quota_percent_left=reg_entry.get("quota_percent_left"),
                    is_expired=reg_is_expired
                )
            )

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
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Quota", justify="right", style="bright_yellow")
    table.add_column("Available", justify="right", style="bright_yellow")
    table.add_column("Session Start", justify="right", style="dim")
    table.add_column("Reset At", justify="right", style="dim")
    table.add_column("Source", style="dim italic")

    for status in statuses:
        account_display = f"[bold]*{status.email}[/]" if status.email == live_email else status.email
        
        if status.is_expired:
            if status.status == "ready":
                status_display = "[bold red]RE-LOGIN[/]"
            else:
                status_display = f"[bold red]RE-LOGIN[/]/[dim]({status.status.upper()})[/]"
        else:
            status_display = f"[bold bright_green]{status.status.upper()}[/]" if status.status == "ready" else f"[bold bright_yellow]{status.status.upper()}[/]"

        quota_display = (
            f"{status.quota_percent_left}%"
            if status.quota_percent_left is not None
            else "unknown"
        )

        table.add_row(
            account_display,
            status_display,
            quota_display,
            format_remaining(status.remaining_seconds),
            status.session_start_at.strftime("%Y-%m-%d %H:%M:%S"),
            status.next_available_at.strftime("%Y-%m-%d %H:%M:%S"),
            status.validation_status,
        )

    console.print(Panel(table, title="[bold bright_cyan]Account Cooldown Status[/]", border_style="bright_cyan", expand=False))


def statuses_to_table(statuses: list[CooldownStatus], live_email: str | None = None) -> str:
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
        
        status_text = status.status.upper()
        if status.is_expired:
            if status.status == "ready":
                status_text = "RE-LOGIN"
            else:
                status_text = f"RE-LOGIN/({status_text})"

        rows.append(
            [
                account_display,
                status_text,
                format_remaining(status.remaining_seconds),
                status.session_start_at.strftime("%Y-%m-%d %H:%M:%S"),
                status.next_available_at.strftime("%Y-%m-%d %H:%M:%S"),
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
