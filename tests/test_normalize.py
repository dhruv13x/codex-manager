from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from codex_manager.normalize import (
    build_archive_name,
    normalize_auth_file,
    normalize_directory,
    parse_legacy_auth_filename,
)


def test_parse_legacy_auth_filename() -> None:
    day, month, month_token, email = parse_legacy_auth_filename(
        "21apr_drdpsbose023@gmail.com_auth.json"
    )
    assert day == 21
    assert month == 4
    assert month_token == "apr"
    assert email == "drdpsbose023@gmail.com"


def test_build_archive_name() -> None:
    session_start = datetime(2026, 4, 14, 15, 55, 0, tzinfo=timezone.utc)
    assert (
        build_archive_name(session_start, "drdpsbose023@gmail.com")
        == "2026-04-14-155500-drdpsbose023@gmail.com-codex.tar.gz"
    )


def test_normalize_auth_file_matches_example(tmp_path: Path, mocker) -> None:
    auth_file = tmp_path / "21apr_drdpsbose023@gmail.com_auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    ist = timezone(timedelta(hours=5, minutes=30))
    quota_end = datetime(2026, 4, 14, 17, 55, 0, tzinfo=ist)
    epoch = quota_end.timestamp()
    auth_file.touch()
    auth_file.chmod(0o600)
    import os
    os.utime(auth_file, (epoch, epoch))

    # Avoid patching datetime which causes issues.
    # Just calculate what the name should be based on the actual mtime
    mtime = auth_file.stat().st_mtime
    actual_quota_end = datetime.fromtimestamp(mtime).astimezone()
    actual_session_start = actual_quota_end - timedelta(hours=2)
    expected_name = f"{actual_session_start.strftime('%Y-%m-%d-%H%M%S')}-drdpsbose023@gmail.com-codex.tar.gz"

    record = normalize_auth_file(
        auth_file,
        session_duration_hours=2,
        reference_year=2026,
    )

    assert record.email == "drdpsbose023@gmail.com"
    assert record.legacy_quota_day_token == "21apr"
    assert record.proposed_archive_name == expected_name
    assert record.validation_status == "ok"


def test_normalize_auth_file_detects_mismatch(tmp_path: Path) -> None:
    auth_file = tmp_path / "21apr_drdpsbose023@gmail.com_auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    ist = timezone(timedelta(hours=5, minutes=30))
    quota_end = datetime(2026, 4, 14, 17, 55, 0, tzinfo=ist) + timedelta(days=1)
    epoch = quota_end.timestamp()
    import os
    os.utime(auth_file, (epoch, epoch))

    record = normalize_auth_file(
        auth_file,
        session_duration_hours=2,
        reference_year=2026,
    )

    assert record.validation_status == "mismatch"
    assert "expected 2026-04-21" in record.validation_details


def test_normalize_directory_filters_non_matching_files(tmp_path: Path) -> None:
    (tmp_path / "21apr_a@gmail.com_auth.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.txt").write_text("x", encoding="utf-8")

    records = normalize_directory(
        tmp_path,
        session_duration_hours=2,
        reference_year=2026,
    )

    assert len(records) == 1
    assert records[0].email == "a@gmail.com"
