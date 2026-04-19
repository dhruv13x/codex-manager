from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import DEFAULT_BACKUP_DIR, DEFAULT_CODEX_HOME

def _check_command(command: str) -> bool:
    try:
        subprocess.run(["which", command], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def _check_dir_writable(path: Path) -> bool:
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False
    return os.access(path, os.W_OK)

def run_doctor(codex_home: Path = DEFAULT_CODEX_HOME, backup_dir: Path = DEFAULT_BACKUP_DIR) -> None:
    print("Codex Manager Doctor\n")

    issues = 0

    print("Checking dependencies...")
    if _check_command("tmux"):
        print("  [OK] tmux is installed")
    else:
        print("  [FAIL] tmux is not found in PATH")
        issues += 1

    if _check_command("codex"):
        print("  [OK] codex is installed")
    else:
        print("  [FAIL] codex is not found in PATH")
        issues += 1

    print("\nChecking directories...")
    if codex_home.exists():
        print(f"  [OK] Codex home ({codex_home}) exists")
    else:
        print(f"  [FAIL] Codex home ({codex_home}) does not exist")
        issues += 1

    if _check_dir_writable(backup_dir):
        print(f"  [OK] Backup directory ({backup_dir}) is writable")
    else:
        print(f"  [FAIL] Backup directory ({backup_dir}) is not writable or cannot be created")
        issues += 1

    print("\nChecking status parser...")
    try:
        from .status import parse_live_status_text
        sample_status = "Email: test@example.com\nQuota: [░] 10% left (resets 10:02 on 26 Apr)"
        parse_live_status_text(sample_status)
        print("  [OK] Status parser is functioning correctly")
    except Exception as e:
        print(f"  [FAIL] Status parser encountered an error: {e}")
        issues += 1

    print(f"\nDoctor check complete. Found {issues} issue(s).")
    if issues > 0:
        sys.exit(1)
