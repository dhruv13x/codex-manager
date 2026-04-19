from __future__ import annotations

from pathlib import Path

from codex_manager.inventory import load_inventory, write_inventory
from codex_manager.normalize import NormalizedRecord


def test_inventory_roundtrip(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    records = [
        NormalizedRecord(
            email="a@example.com",
            legacy_auth_filename="21apr_a@example.com_auth.json",
            legacy_quota_day_token="21apr",
            quota_end_detected_at="2026-04-14T17:55:00+05:30",
            session_start_at="2026-04-14T15:55:00+05:30",
            next_available_at="2026-04-21T15:55:00+05:30",
            inferred_session_duration_seconds=7200,
            proposed_archive_name="2026-04-14-155500-a@example.com-codex.tar.gz",
            validation_status="ok",
            validation_details="ok",
            source_path=".codex_sample/21apr_a@example.com_auth.json",
        )
    ]

    write_inventory(records, inventory_path)
    loaded = load_inventory(inventory_path)

    assert loaded == records
