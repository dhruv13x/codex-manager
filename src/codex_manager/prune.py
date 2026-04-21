from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

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


def prune_result_to_text(plan: PrunePlan, *, dry_run: bool, source_dir: Path | None = None) -> str | object:
    try:
        from rich.panel import Panel
        from rich.text import Text

        t = Text()
        mode_color = "yellow" if dry_run else "green"
        t.append("mode: ", style="bold")
        t.append(f"{'dry-run' if dry_run else 'pruned'}\n", style=mode_color)
        if source_dir is not None:
            t.append("source_dir: ", style="bold")
            t.append(f"{source_dir}\n", style="cyan")

        t.append("files_removed: ", style="bold")
        t.append(f"{len(plan.files)}\n")
        for path in plan.files:
            t.append(f"  file: {path}\n", style="dim")

        t.append("directories_removed: ", style="bold")
        t.append(f"{len(plan.directories)}\n")
        for path in plan.directories:
            t.append(f"  dir: {path}\n", style="dim")

        t.append("preserved: ", style="bold")
        t.append("auth.json, config.toml, installation_id, version.json, current auth/account state")

        return Panel(t, title="Prune Result", border_style="blue")
    except ImportError:
        pass

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
