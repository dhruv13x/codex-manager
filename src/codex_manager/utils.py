from __future__ import annotations

from datetime import datetime


def isoformat_local(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.astimezone().isoformat(timespec="seconds")
    return dt.isoformat(timespec="seconds")


def build_archive_name(session_start_at: datetime, email: str) -> str:
    return f"{session_start_at.strftime('%Y-%m-%d-%H%M%S')}-{email}-codex.tar.gz"
