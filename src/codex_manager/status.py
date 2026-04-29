from __future__ import annotations

import re
import shlex
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from .ui import console
from .utils import build_archive_name, isoformat_local

STATUS_PANEL_ACCOUNT_RE = re.compile(r"Account:\s+(\S+@\S+)")
STATUS_PANEL_WEEKLY_RE = re.compile(r"Weekly limit:\s+(.*?)(?:\n|$)", re.DOTALL)
STATUS_REFRESH_RE = re.compile(r"refresh requested", re.IGNORECASE)
TOKEN_EXPIRED_RE = re.compile(r"(token_expired|authentication token is expired|signing in again)", re.IGNORECASE)

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


class TokenExpiredError(RuntimeError):
    def __init__(self, message: str, output: str):
        super().__init__(message)
        self.output = output


@dataclass(frozen=True)
class LiveStatus:
    email: str
    reset_at: datetime
    session_start_at: datetime
    quota_text: str
    quota_percent_left: int | None
    proposed_archive_name: str
    is_expired: bool = False


def run_command(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def run_status_command(command: str) -> str:
    result = subprocess.run(
        shlex.split(command),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Status command failed with exit code {result.returncode}:\n{result.stderr}"
        )
    return result.stdout


def capture_tmux_status_text(
    *,
    session_name: str | None = None,
    codex_command: str = "codex --no-alt-screen",
    cols: int = 120,
    rows: int = 40,
    startup_timeout_seconds: float = 20.0,
    status_timeout_seconds: float = 20.0,
) -> str:
    # 1. Verification: Is tmux available?
    try:
        subprocess.run(["tmux", "-V"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("tmux is not installed or not in PATH. It is required for live status capture.") from None

    # 2. Setup unique session name if not provided
    if session_name is None:
        import os
        session_name = f"cm_capture_{os.getpid()}"

    # 3. Clean start: Only kill if it exists and it's ours (simple check)
    has_session = subprocess.run(["tmux", "has-session", "-t", session_name], capture_output=True).returncode == 0
    if has_session:
        run_command(["tmux", "kill-session", "-t", session_name], check=False)

    session = run_command(
        [
            "tmux",
            "new-session",
            "-d",
            "-P",
            "-F",
            "#{pane_id}",
            "-s",
            session_name,
            "-x",
            str(cols),
            "-y",
            str(rows),
            codex_command,
        ]
    )
    pane_id = session.stdout.strip()
    if not pane_id:
        raise RuntimeError("tmux did not return a pane id for the temporary capture session.")
    run_command(["tmux", "set-option", "-t", session_name, "remain-on-exit", "on"])

    try:
        start = time.time()
        with console.status("[cyan]Waiting for Codex prompt...[/cyan]", spinner="dots"):
            while True:
                output = run_command(["tmux", "capture-pane", "-t", pane_id, "-p"]).stdout
                if "›" in output:
                    break
                
                if time.time() - start > startup_timeout_seconds:
                    raise RuntimeError("Timed out waiting for Codex prompt.")
                time.sleep(0.5)

        run_command(["tmux", "send-keys", "-t", pane_id, "/status", "Enter"])

        start = time.time()
        last_retry = start
        with console.status("[cyan]Checking Codex status...[/cyan]", spinner="dots"):
            while True:
                output = run_command(["tmux", "capture-pane", "-t", pane_id, "-p"]).stdout
                
                # If we have the full panel, return it
                if "Account:" in output and "Weekly limit:" in output:
                    return output

                # Check for token expiry, but ensure we have the Account string if possible
                if TOKEN_EXPIRED_RE.search(output) and "Account:" in output:
                    raise TokenExpiredError("Codex authentication token is expired.", output)

                # Handle 'refresh requested' or missing quota data or token expired without Account
                elapsed = time.time() - start
                if elapsed > status_timeout_seconds:
                    if TOKEN_EXPIRED_RE.search(output):
                        raise TokenExpiredError("Codex authentication token is expired.", output)
                    if "Account:" in output and (STATUS_REFRESH_RE.search(output) or "refresh" in output.lower()):
                        return output # Return what we have so we can at least get the email
                    raise RuntimeError("Timed out waiting for Codex status panel.")

                # Periodic retry of /status if it seems stuck or refreshing
                if time.time() - last_retry > 5.0:
                    run_command(["tmux", "send-keys", "-t", pane_id, "/status", "Enter"])
                    last_retry = time.time()
                
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
    if account_match:
        email = account_match.group(1)
        quota = weekly_match.group(1).strip() if weekly_match else "Status refreshing or token expired."
        return email, quota

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
            # If we can't parse a reset time (e.g. token expired), default to now
            return now

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
    
    is_expired = TOKEN_EXPIRED_RE.search(text) is not None
    
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
        is_expired=is_expired,
    )


def live_status_to_text(status: LiveStatus) -> str:
    lines = [
        f"email: {status.email}",
        f"reset_at: {status.reset_at.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"session_start_at: {status.session_start_at.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"quota_text: {status.quota_text}",
        f"quota_percent_left: {status.quota_percent_left if status.quota_percent_left is not None else 'unknown'}",
        f"archive_name: {status.proposed_archive_name}",
        f"reset_at_iso: {isoformat_local(status.reset_at)}",
        f"session_start_at_iso: {isoformat_local(status.session_start_at)}",
        f"is_expired: {status.is_expired}",
    ]
    return "\n".join(lines)
