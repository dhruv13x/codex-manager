from __future__ import annotations

import os
import re
from pathlib import Path

CODEX_MANAGER_HOME = Path(
    os.path.expanduser(os.environ.get("CODEXMGR_HOME", "~/.codexmgr"))
)
DEFAULT_CODEX_HOME = Path(os.path.expanduser("~/.codex"))
DEFAULT_SAMPLE_HOME = Path(".codex_sample")
DEFAULT_INVENTORY_PATH = CODEX_MANAGER_HOME / "inventory.json"
DEFAULT_BACKUP_DIR = CODEX_MANAGER_HOME / "backups"
DEFAULT_COOLDOWN_DISPLAY_LIMIT = 200
DEFAULT_SESSION_DURATION_HOURS = 2.0
DEFAULT_REFERENCE_YEAR = 2026

LEGACY_AUTH_FILENAME_RE = re.compile(
    r"^(?P<day>\d{1,2})(?P<month>[a-z]{3})_(?P<email>.+)_auth\.json$",
    re.IGNORECASE,
)

NORMALIZED_ARCHIVE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{6}-.+-codex\.tar\.gz$"
)

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

def load_config() -> dict[str, str | int | float | bool]:
    import json
    config_path = CODEX_MANAGER_HOME / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
