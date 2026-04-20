from __future__ import annotations

import os
from pathlib import Path

CODEX_MANAGER_HOME = Path(
    os.path.expanduser(os.environ.get("CODEXMGR_HOME", "~/.codexmgr"))
)
DEFAULT_CODEX_HOME = Path(os.path.expanduser("~/.codex"))
DEFAULT_BACKUP_DIR = CODEX_MANAGER_HOME / "backups"
DEFAULT_COOLDOWN_DISPLAY_LIMIT = 200

def load_config() -> dict[str, str | int | float | bool]:
    import json
    config_path = CODEX_MANAGER_HOME / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
