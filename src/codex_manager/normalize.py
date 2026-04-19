from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from .config import LEGACY_AUTH_FILENAME_RE, MONTH_LOOKUP, NORMALIZED_ARCHIVE_RE


@dataclass(frozen=True)
class NormalizedRecord:
    email: str
    legacy_auth_filename: str
    legacy_quota_day_token: str
    quota_end_detected_at: str
    session_start_at: str
    next_available_at: str
    inferred_session_duration_seconds: int
    proposed_archive_name: str
    validation_status: str
    validation_details: str
    source_path: str


def parse_legacy_auth_filename(filename: str) -> tuple[int, int, str, str]:
    match = LEGACY_AUTH_FILENAME_RE.match(filename)
    if not match:
        raise ValueError(f"Unsupported legacy auth filename: {filename}")

    day = int(match.group("day"))
    month_token = match.group("month").lower()
    email = match.group("email")
    month = MONTH_LOOKUP.get(month_token)
    if month is None:
        raise ValueError(f"Unsupported month token in filename: {filename}")

    return day, month, month_token, email


def isoformat_local(dt: datetime) -> str:
    return dt.astimezone().isoformat(timespec="seconds")


def build_archive_name(session_start_at: datetime, email: str) -> str:
    name = f"{session_start_at.strftime('%Y-%m-%d-%H%M%S')}-{email}-codex.tar.gz"
    if not NORMALIZED_ARCHIVE_RE.match(name):
        raise ValueError(f"Generated invalid archive name: {name}")
    return name


def normalize_auth_file(
    auth_path: Path,
    *,
    session_duration_hours: float,
    reference_year: int,
) -> NormalizedRecord:
    day, month, month_token, email = parse_legacy_auth_filename(auth_path.name)
    quota_end_detected_at = datetime.fromtimestamp(auth_path.stat().st_mtime).astimezone()
    session_start_at = quota_end_detected_at - timedelta(hours=session_duration_hours)
    next_available_at = session_start_at + timedelta(days=7)
    target_date = datetime(reference_year, month, day).date()

    if next_available_at.date() == target_date:
        validation_status = "ok"
        validation_details = "Legacy quota-day token matches computed next availability date."
    else:
        validation_status = "mismatch"
        validation_details = (
            "Legacy quota-day token does not match computed next availability date: "
            f"expected {target_date.isoformat()}, got {next_available_at.date().isoformat()}."
        )

    return NormalizedRecord(
        email=email,
        legacy_auth_filename=auth_path.name,
        legacy_quota_day_token=f"{day:02d}{month_token}",
        quota_end_detected_at=isoformat_local(quota_end_detected_at),
        session_start_at=isoformat_local(session_start_at),
        next_available_at=isoformat_local(next_available_at),
        inferred_session_duration_seconds=int(session_duration_hours * 3600),
        proposed_archive_name=build_archive_name(session_start_at, email),
        validation_status=validation_status,
        validation_details=validation_details,
        source_path=str(auth_path),
    )


def iter_legacy_auth_files(source_dir: Path) -> Iterable[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    for path in sorted(source_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and LEGACY_AUTH_FILENAME_RE.match(path.name):
            yield path


def normalize_directory(
    source_dir: Path,
    *,
    session_duration_hours: float,
    reference_year: int,
) -> list[NormalizedRecord]:
    return [
        normalize_auth_file(
            path,
            session_duration_hours=session_duration_hours,
            reference_year=reference_year,
        )
        for path in iter_legacy_auth_files(source_dir)
    ]


def records_to_json(records: list[NormalizedRecord]) -> str:
    import json

    return json.dumps([asdict(record) for record in records], indent=2)
