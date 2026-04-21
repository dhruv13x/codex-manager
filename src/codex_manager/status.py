from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .utils import build_archive_name, isoformat_local

STATUS_PANEL_ACCOUNT_RE = re.compile(r"Account:\s+(\S+@\S+)")
STATUS_PANEL_WEEKLY_RE = re.compile(r"Weekly limit:\s+(.*?)(?:\n|$)", re.DOTALL)
SCRIPT_EMAIL_RE = re.compile(r"Email\s*:\s*(\S+@\S+)")
SCRIPT_QUOTA_RE = re.compile(r"Quota\s*:\s*(.+)")
RESET_TEXT_RE = re.compile(
    r"resets\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+on\s+(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3})",
    re.IGNORECASE,
)
RESET_TIME_ONLY_RE = re.compile(
    r"resets\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"(\d+)%\s+left")

MONTH_LOOKUP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(frozen=True)
class LiveStatus:
    email: str
    reset_at: datetime
    session_start_at: datetime
    quota_text: str
    quota_percent_left: int | None
    proposed_archive_name: str


def run_command(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def capture_tmux_status_text(
    *,
    session_name: str = "codex_manager_capture",
    codex_command: str = "codex --no-alt-screen",
    cols: int = 120,
    rows: int = 40,
    startup_timeout_seconds: float = 20.0,
    status_timeout_seconds: float = 20.0,
) -> str:
    run_command(["tmux", "kill-session", "-t", session_name], check=False)
    run_command(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session_name,
            "-x",
            str(cols),
            "-y",
            str(rows),
            codex_command,
        ]
    )

    try:
        start = time.time()
        while True:
            output = run_command(["tmux", "capture-pane", "-t", session_name, "-p"]).stdout
            if "›" in output:
                break
            if time.time() - start > startup_timeout_seconds:
                raise RuntimeError("Timed out waiting for Codex prompt.")
            time.sleep(0.5)

        run_command(["tmux", "send-keys", "-t", session_name, "/status", "Enter"])

        start = time.time()
        retry_sent = False
        while True:
            output = run_command(["tmux", "capture-pane", "-t", session_name, "-p"]).stdout
            if "Account:" in output and "Weekly limit:" in output:
                return output

            elapsed = time.time() - start
            if elapsed > 5 and not retry_sent:
                run_command(["tmux", "send-keys", "-t", session_name, "/status", "Enter"])
                retry_sent = True
            if elapsed > status_timeout_seconds:
                raise RuntimeError("Timed out waiting for Codex status panel.")
            time.sleep(0.5)
    finally:
        run_command(["tmux", "kill-session", "-t", session_name], check=False)


def _extract_email_and_quota(text: str) -> tuple[str, str]:
    email_match = SCRIPT_EMAIL_RE.search(text)
    quota_match = SCRIPT_QUOTA_RE.search(text)
    if email_match and quota_match:
        return email_match.group(1), quota_match.group(1).strip()

    account_match = STATUS_PANEL_ACCOUNT_RE.search(text)
    weekly_match = STATUS_PANEL_WEEKLY_RE.search(text)
    if account_match and weekly_match:
        return account_match.group(1), weekly_match.group(1).strip()

    raise ValueError("Unable to parse Codex status text for email and quota.")


def _resolve_reset_at(quota_text: str, *, now: datetime, reference_year: int | None) -> datetime:
    match = RESET_TEXT_RE.search(quota_text)
    if match:
        month = MONTH_LOOKUP[match.group("month").lower()]
        year = reference_year if reference_year is not None else now.year
        reset_at = datetime(
            year,
            month,
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            tzinfo=now.tzinfo,
        )
    else:
        match = RESET_TIME_ONLY_RE.search(quota_text)
        if not match:
            raise ValueError(f"Unable to parse reset time from quota text: {quota_text}")

        reset_at = datetime(
            now.year,
            now.month,
            now.day,
            int(match.group("hour")),
            int(match.group("minute")),
            tzinfo=now.tzinfo,
        )

    if reference_year is None and reset_at < now - timedelta(days=1):
        reset_at = reset_at.replace(year=reset_at.year + 1)
    return reset_at


def parse_live_status_text(
    text: str,
    *,
    now: datetime | None = None,
    reference_year: int | None = None,
) -> LiveStatus:
    current = now if now is not None else datetime.now().astimezone()
    email, quota_text = _extract_email_and_quota(text)
    reset_at = _resolve_reset_at(quota_text, now=current, reference_year=reference_year)
    session_start_at = reset_at - timedelta(days=7)
    percent_match = PERCENT_RE.search(quota_text)
    quota_percent_left = int(percent_match.group(1)) if percent_match else None

    return LiveStatus(
        email=email,
        reset_at=reset_at,
        session_start_at=session_start_at,
        quota_text=quota_text,
        quota_percent_left=quota_percent_left,
        proposed_archive_name=build_archive_name(session_start_at, email),
    )


def live_status_to_text(status: LiveStatus) -> Any:
    from .rich_utils import create_table

    headers = ["Field", "Value"]
    rows = [
        ["Email", status.email],
        ["Session Start", status.session_start_at.strftime("%Y-%m-%d %H:%M:%S %z")],
        ["Reset At", status.reset_at.strftime("%Y-%m-%d %H:%M:%S %z")],
        ["Quota % Left", f"{status.quota_percent_left}%" if status.quota_percent_left is not None else "unknown"],
        ["Quota Text", status.quota_text],
    ]
    return create_table(title="Live Status", headers=headers, rows=rows)
