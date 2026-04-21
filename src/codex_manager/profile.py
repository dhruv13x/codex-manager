from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from .config import CODEX_MANAGER_HOME


def export_profile(export_path: Path) -> None:
    if not CODEX_MANAGER_HOME.exists():
        raise FileNotFoundError(f"Codex manager home not found: {CODEX_MANAGER_HOME}")

    export_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(export_path, "w:gz") as tar:
        tar.add(CODEX_MANAGER_HOME, arcname=CODEX_MANAGER_HOME.name)


def import_profile(import_path: Path) -> None:
    if not import_path.exists():
        raise FileNotFoundError(f"Profile archive not found: {import_path}")

    # Backup existing first if it exists
    if CODEX_MANAGER_HOME.exists():
        backup_path = CODEX_MANAGER_HOME.with_name(f"{CODEX_MANAGER_HOME.name}.bak")
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.move(CODEX_MANAGER_HOME, backup_path)
        from .ui import console
        console.print(f"Backed up existing profile to {backup_path}")

    with tarfile.open(import_path, "r:gz") as tar:
        # Extract into parent directory since the archive contains the root folder
        tar.extractall(path=CODEX_MANAGER_HOME.parent, filter="data")
