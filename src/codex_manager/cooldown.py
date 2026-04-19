from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .normalize import NormalizedRecord


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


def evaluate_record(record: NormalizedRecord, now: datetime | None = None) -> CooldownStatus:
    current = now.astimezone() if now is not None else datetime.now().astimezone()
    session_start_at = parse_iso_datetime(record.session_start_at)
    next_available_at = parse_iso_datetime(record.next_available_at)
    quota_end_detected_at = parse_iso_datetime(record.quota_end_detected_at)
    remaining_seconds = int((next_available_at - current).total_seconds())
    status = "ready" if remaining_seconds <= 0 else "cooldown"

    return CooldownStatus(
        email=record.email,
        status=status,
        session_start_at=session_start_at,
        next_available_at=next_available_at,
        quota_end_detected_at=quota_end_detected_at,
        validation_status=record.validation_status,
        proposed_archive_name=record.proposed_archive_name,
        remaining_seconds=max(0, remaining_seconds),
    )


def evaluate_records(
    records: list[NormalizedRecord],
    now: datetime | None = None,
    live_status: CooldownStatus | None = None,
) -> list[CooldownStatus]:
    statuses = [evaluate_record(record, now=now) for record in records]

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


def statuses_to_table(statuses: list[CooldownStatus], live_email: str | None = None) -> str:
    headers = [
        "Account",
        "Status",
        "Available",
        "Session Start",
        "Quota End",
        "Valid",
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
