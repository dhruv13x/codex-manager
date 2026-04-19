from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_CODEX_HOME

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


def prune_result_to_text(plan: PrunePlan, *, dry_run: bool, source_dir: Path | None = None) -> str:
    lines = [
        f"mode: {'dry-run' if dry_run else 'pruned'}",
    ]
    if source_dir is not None:
        lines.append(f"source_dir: {source_dir}")
    lines.append(f"files_removed: {len(plan.files)}")
    lines.extend(f"file: {path}" for path in plan.files)
    lines.append(f"directories_removed: {len(plan.directories)}")
    lines.extend(f"dir: {path}" for path in plan.directories)
    lines.append("preserved: auth.json, config.toml, installation_id, version.json, current auth/account state")
    return "\n".join(lines)
