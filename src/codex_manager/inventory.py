from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .normalize import NormalizedRecord, isoformat_local


def build_inventory_payload(records: list[NormalizedRecord]) -> dict:
    return {
        "generated_at": isoformat_local(datetime.now().astimezone()),
        "record_count": len(records),
        "records": [asdict(record) for record in records],
    }


def write_inventory(records: list[NormalizedRecord], inventory_path: Path) -> None:
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps(build_inventory_payload(records), indent=2),
        encoding="utf-8",
    )


def load_inventory(inventory_path: Path) -> list[NormalizedRecord]:
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    raw_records = payload.get("records", [])
    if not isinstance(raw_records, list):
        raise ValueError(f"Invalid inventory payload in {inventory_path}")
    return [NormalizedRecord(**record) for record in raw_records]
