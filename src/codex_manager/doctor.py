from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from .cloud import get_cloud_provider
from .config import DEFAULT_BACKUP_DIR, DEFAULT_CODEX_HOME
from .ui import Table, console


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

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    issues = 0

    # Dependencies
    for cmd in ["tmux", "codex"]:
        if _check_command(cmd):
            # Resolve path for details
            path = subprocess.run(["which", cmd], capture_output=True, text=True).stdout.strip()
            table.add_row(f"Tool: {cmd}", "[bold green]OK[/]", path)
        else:
            table.add_row(f"Tool: {cmd}", "[bold red]FAIL[/]", "Not found in PATH")
            issues += 1

    try:
        import importlib.util
        importlib.util.find_spec("boto3")
        table.add_row("Lib: boto3", "[bold green]OK[/]", "Installed")
    except ImportError:
        table.add_row("Lib: boto3", "[bold red]FAIL[/]", "Not installed")
        issues += 1

    try:
        import importlib.util
        importlib.util.find_spec("b2sdk")
        table.add_row("Lib: b2sdk", "[bold green]OK[/]", "Installed")
    except ImportError:
        table.add_row("Lib: b2sdk", "[bold red]FAIL[/]", "Not installed")
        issues += 1

    # Directories
    if codex_home.exists():
        table.add_row("Dir: Codex Home", "[bold green]OK[/]", f"Exists: {codex_home}")
    else:
        table.add_row("Dir: Codex Home", "[bold red]FAIL[/]", f"Missing: {codex_home}")
        issues += 1

    if _check_dir_writable(backup_dir):
        table.add_row("Dir: Backup Dir", "[bold green]OK[/]", f"Writable: {backup_dir}")
    else:
        table.add_row("Dir: Backup Dir", "[bold red]FAIL[/]", f"Not writable: {backup_dir}")
        issues += 1

    # Network
    try:
        urllib.request.urlopen("https://www.google.com", timeout=3)
        table.add_row("Network", "[bold green]OK[/]", "Internet accessible")
    except Exception:
        table.add_row("Network", "[bold red]FAIL[/]", "No internet access")
        issues += 1

    # Cloud (B2)
    try:
        cp = get_cloud_provider()
        if cp:
            table.add_row("Cloud (B2)", "[bold green]OK[/]", f"Authenticated (Bucket: {cp.bucket_name})")
        else:
            table.add_row("Cloud (B2)", "[yellow]SKIPPED[/]", "Credentials not configured")
    except Exception as e:
        table.add_row("Cloud (B2)", "[bold red]FAIL[/]", str(e))
        issues += 1

    # Status Parser
    try:
        from .status import parse_live_status_text
        sample_status = "Email: test@example.com\nQuota: [░] 10% left (resets 10:02 on 26 Apr)"
        parse_live_status_text(sample_status)
        table.add_row("Status Parser", "[bold green]OK[/]", "Functioning correctly")
    except Exception as e:
        table.add_row("Status Parser", "[bold red]FAIL[/]", str(e))
        issues += 1

    console.print(table)
    console.print(f"\n[bold]Doctor check complete. Found {issues} issue(s).[/]")
    if issues > 0:
        sys.exit(1)
