from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FILE_GLOBS = [
    "state_5.sqlite*",
    "logs_*",
    "models_cache.json",
    "history.jsonl",
]

DIRECTORY_NAMES = [
    "cache",
    "tmp",
    ".tmp",
    "memories",
    "skills",
    "shell_snapshots",
    "log",
    "sessions",
]


@dataclass(frozen=True)
class PrunePlan:
    files: list[Path]
    directories: list[Path]


def build_prune_plan(source_dir: Path) -> PrunePlan:
    files: list[Path] = []
    directories: list[Path] = []

    for pattern in FILE_GLOBS:
        files.extend(sorted(source_dir.glob(pattern), key=lambda path: path.name))

    for name in DIRECTORY_NAMES:
        path = source_dir / name
        if path.exists():
            directories.append(path)

    return PrunePlan(files=files, directories=directories)


def perform_prune(args) -> PrunePlan:
    source_dir = Path(args.source_dir).expanduser()
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Codex directory does not exist: {source_dir}")

    plan = build_prune_plan(source_dir)
    if args.dry_run:
        return plan

    for path in plan.files:
        if path.exists():
            path.unlink()

    for path in plan.directories:
        if path.exists():
            shutil.rmtree(path)

    return plan


def prune_result_to_text(plan: PrunePlan, *, dry_run: bool, source_dir: Path | None = None) -> Any:
    from .rich_utils import create_table

    headers = ["Type", "Path"]
    rows = []

    mode = f"[bold yellow]{'dry-run'}[/]" if dry_run else "[bold green]pruned[/]"

    rows.append(["Mode", mode])
    if source_dir:
        rows.append(["Source Dir", str(source_dir)])

    rows.append(["Files Removed", str(len(plan.files))])
    for path in plan.files:
        rows.append(["File", str(path)])

    rows.append(["Directories Removed", str(len(plan.directories))])
    for path in plan.directories:
        rows.append(["Dir", str(path)])

    rows.append(["Preserved", "auth.json, config.toml, installation_id, version.json, current auth/account state"])

    return create_table(title="Prune Result", headers=headers, rows=rows)
