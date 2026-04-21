from __future__ import annotations

import os
from pathlib import Path

# Primary environment variable: CODEX_MANAGER_HOME
# Primary directory: ~/.codex-manager

_env_home = os.environ.get("CODEX_MANAGER_HOME")
if _env_home:
    CODEX_MANAGER_HOME = Path(os.path.expanduser(_env_home))
else:
    CODEX_MANAGER_HOME = Path(os.path.expanduser("~/.codex-manager"))

DEFAULT_BACKUP_DIR = CODEX_MANAGER_HOME / "backups"
COOLDOWN_REGISTRY_PATH = CODEX_MANAGER_HOME / "cooldown.json"

_env_codex_home = os.environ.get("CODEX_HOME")
if _env_codex_home:
    DEFAULT_CODEX_HOME = Path(os.path.expanduser(_env_codex_home))
else:
    DEFAULT_CODEX_HOME = Path(os.path.expanduser("~/.codex"))

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
