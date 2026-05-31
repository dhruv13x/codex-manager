from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

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
    plan_type: str = "unknown"
    access_token_expires_at: str | None = None
    auth_expires_at: str | None = None


def parse_iso_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    
    val_str = str(value).strip()
    if not val_str or val_str.lower() in ("none", "unknown", "null"):
        # Default to epoch if unknown
        return datetime.fromtimestamp(0).astimezone()

    try:
        dt = datetime.fromisoformat(val_str)
        if dt.tzinfo is None:
            return dt.astimezone()
        return dt
    except ValueError:
        return datetime.fromtimestamp(0).astimezone()


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
        plan_type=getattr(entry, "plan_type", "unknown"),
        access_token_expires_at=getattr(entry, "access_token_expires_at", None),
        auth_expires_at=getattr(entry, "auth_expires_at", None)
        or getattr(entry, "access_token_expires_at", None),
    )


def evaluate_records(
    entries: list[BackupEntry],
    now: datetime | None = None,
    live_status: CooldownStatus | None = None,
) -> list[CooldownStatus]:
    statuses = [evaluate_entry(entry, now=now) for entry in entries]
    
    # Merge with registry
    from .registry import get_active_account, load_registry
    registry_data = load_registry()
    active_email = get_active_account()
    
    current = now.astimezone() if now is not None else datetime.now().astimezone()
    
    for email, reg_entry in registry_data.items():
        if email.startswith("_"):
            continue
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
                    is_expired=reg_is_expired,
                    plan_type=reg_entry.get("plan_type", existing_status.plan_type),
                    access_token_expires_at=reg_entry.get("access_token_expires_at", existing_status.access_token_expires_at),
                    auth_expires_at=reg_entry.get("auth_expires_at")
                    or reg_entry.get("access_token_expires_at")
                    or existing_status.auth_expires_at,
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
                    is_expired=reg_is_expired,
                    plan_type=reg_entry.get("plan_type", "unknown"),
                    access_token_expires_at=reg_entry.get("access_token_expires_at"),
                    auth_expires_at=reg_entry.get("auth_expires_at")
                    or reg_entry.get("access_token_expires_at"),
                )
            )

    if live_status is not None:
        # replace any historical status for the live account
        statuses = [s for s in statuses if s.email != live_status.email]
        statuses.append(live_status)

    final_statuses = []
    for s in statuses:
        if s.email == active_email:
            final_statuses.append(
                CooldownStatus(
                    email=s.email,
                    status="active",
                    session_start_at=s.session_start_at,
                    next_available_at=s.next_available_at,
                    quota_end_detected_at=s.quota_end_detected_at,
                    validation_status=s.validation_status,
                    proposed_archive_name=s.proposed_archive_name,
                    remaining_seconds=s.remaining_seconds,
                    quota_text=s.quota_text,
                    quota_percent_left=s.quota_percent_left,
                    is_expired=s.is_expired,
                    plan_type=s.plan_type,
                    access_token_expires_at=s.access_token_expires_at,
                    auth_expires_at=s.auth_expires_at,
                )
            )
        else:
            final_statuses.append(s)

    return sorted(
        final_statuses,
        key=lambda item: (
            item.status != "active",
            item.status != "ready",
            item.is_expired,
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


def format_compact_duration(seconds: int) -> str:
    seconds = max(0, seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def format_auth_state(expires_at: str | None, now: datetime | None = None) -> str:
    if not expires_at:
        return "Unknown"

    try:
        expires = datetime.fromisoformat(expires_at)
    except ValueError:
        return "Unknown"

    current = now.astimezone() if now is not None else datetime.now().astimezone()
    if expires.tzinfo is None:
        expires = expires.astimezone()

    remaining_seconds = int((expires - current).total_seconds())
    if remaining_seconds <= 0:
        return f"Expired {format_compact_duration(abs(remaining_seconds))}"
    if remaining_seconds < 24 * 60 * 60:
        return f"Expiring {format_compact_duration(remaining_seconds)}"
    return f"Valid {format_compact_duration(remaining_seconds)}"


def format_quota_display(
    quota_percent_left: int | None,
    plan_type: str | None,
    *,
    rich_markup: bool = False,
) -> str:
    quota = f"{quota_percent_left}%" if quota_percent_left is not None else "unknown"
    plan = (plan_type or "").strip().lower()
    if plan in {"", "unknown", "free"}:
        return quota
    suffix = f"({plan})"
    if rich_markup:
        suffix = f"[dim]{suffix}[/]"
    return f"{quota} {suffix}"


def print_statuses_table(statuses: list[CooldownStatus], live_email: str | None = None) -> None:
    from .ui import Panel, Table, console

    table = Table(show_header=True, header_style="bold bright_magenta")
    table.add_column("Account", style="bright_cyan")
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Quota", justify="right", style="bright_yellow")
    table.add_column("Available", justify="right", style="bright_yellow")
    table.add_column("Auth State", justify="right", no_wrap=True)

    for status in statuses:
        account_display = f"[bold]*{status.email}[/]" if status.email == live_email else status.email
        
        if status.status == "active":
            status_display = "[bold bright_red]ACTIVE[/]"
            if status.is_expired:
                status_display = "[bold red]ACTIVE (EXPIRED)[/]"
        elif status.is_expired:
            if status.status == "ready":
                status_display = "[bold red]RE-LOGIN[/]"
            else:
                status_display = f"[bold red]RE-LOGIN[/]/[dim]({status.status.upper()})[/]"
        else:
            status_display = f"[bold bright_green]{status.status.upper()}[/]" if status.status == "ready" else f"[bold bright_yellow]{status.status.upper()}[/]"

        quota_display = format_quota_display(
            status.quota_percent_left,
            status.plan_type,
            rich_markup=True,
        )

        auth_state = format_auth_state(status.auth_expires_at)
        if auth_state.startswith("Expired"):
            auth_state = f"[bold red]{auth_state}[/]"
        elif auth_state.startswith("Expiring"):
            auth_state = f"[bold yellow]{auth_state}[/]"
        elif auth_state.startswith("Valid"):
            auth_state = f"[green]{auth_state}[/]"
        else:
            auth_state = f"[dim]{auth_state}[/]"

        table.add_row(
            account_display,
            status_display,
            quota_display,
            format_remaining(status.remaining_seconds),
            auth_state,
        )

    console.print(Panel(table, title="[bold bright_cyan]Account Cooldown Status[/]", border_style="bright_cyan", expand=False))


def statuses_to_table(statuses: list[CooldownStatus], live_email: str | None = None) -> str:
    headers = [
        "Account",
        "Status",
        "Quota",
        "Available",
        "Auth State",
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

        quota_display = format_quota_display(status.quota_percent_left, status.plan_type)

        auth_state = format_auth_state(status.auth_expires_at)

        rows.append(
            [
                account_display,
                status_text,
                quota_display,
                format_remaining(status.remaining_seconds),
                auth_state,
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
