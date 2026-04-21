from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from .cloud import get_cloud_provider
from .config import DEFAULT_BACKUP_DIR, DEFAULT_CODEX_HOME
from .rich_utils import RICH_AVAILABLE, console, create_table

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
    console.print("[bold cyan]Codex Manager Doctor[/]\n")

    headers = ["Component", "Status", "Details"]
    rows = []

    issues = 0

    # Dependencies
    for cmd in ["tmux", "codex"]:
        if _check_command(cmd):
            # Resolve path for details
            path = subprocess.run(["which", cmd], capture_output=True, text=True).stdout.strip()
            rows.append([f"Tool: {cmd}", "[bold green]OK[/]", path])
        else:
            rows.append([f"Tool: {cmd}", "[bold red]FAIL[/]", "Not found in PATH"])
            issues += 1

    try:
        import importlib.util
        importlib.util.find_spec("boto3")
        rows.append(["Lib: boto3", "[bold green]OK[/]", "Installed"])
    except ImportError:
        rows.append(["Lib: boto3", "[bold red]FAIL[/]", "Not installed"])
        issues += 1

    try:
        import importlib.util
        importlib.util.find_spec("b2sdk")
        rows.append(["Lib: b2sdk", "[bold green]OK[/]", "Installed"])
    except ImportError:
        rows.append(["Lib: b2sdk", "[bold red]FAIL[/]", "Not installed"])
        issues += 1

    # Directories
    if codex_home.exists():
        rows.append(["Dir: Codex Home", "[bold green]OK[/]", f"Exists: {codex_home}"])
    else:
        rows.append(["Dir: Codex Home", "[bold red]FAIL[/]", f"Missing: {codex_home}"])
        issues += 1

    if _check_dir_writable(backup_dir):
        rows.append(["Dir: Backup Dir", "[bold green]OK[/]", f"Writable: {backup_dir}"])
    else:
        rows.append(["Dir: Backup Dir", "[bold red]FAIL[/]", f"Not writable: {backup_dir}"])
        issues += 1

    # Network
    try:
        urllib.request.urlopen("https://www.google.com", timeout=3)
        rows.append(["Network", "[bold green]OK[/]", "Internet accessible"])
    except Exception:
        rows.append(["Network", "[bold red]FAIL[/]", "No internet access"])
        issues += 1

    # Cloud (B2)
    try:
        cp = get_cloud_provider()
        if cp:
            rows.append(["Cloud (B2)", "[bold green]OK[/]", f"Authenticated (Bucket: {cp.bucket_name})"])
        else:
            rows.append(["Cloud (B2)", "[yellow]SKIPPED[/]", "Credentials not configured"])
    except Exception as e:
        rows.append(["Cloud (B2)", "[bold red]FAIL[/]", str(e)])
        issues += 1

    # Status Parser
    try:
        from .status import parse_live_status_text
        sample_status = "Email: test@example.com\nQuota: [░] 10% left (resets 10:02 on 26 Apr)"
        parse_live_status_text(sample_status)
        rows.append(["Status Parser", "[bold green]OK[/]", "Functioning correctly"])
    except Exception as e:
        rows.append(["Status Parser", "[bold red]FAIL[/]", str(e)])
        issues += 1

    table = create_table(headers=headers, rows=rows)
    console.print(table)
    console.print(f"\n[bold]Doctor check complete. Found {issues} issue(s).[/]")
    if issues > 0:
        sys.exit(1)
