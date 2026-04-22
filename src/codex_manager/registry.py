from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import COOLDOWN_REGISTRY_PATH

if TYPE_CHECKING:
    from .cloud import B2Provider


def load_registry() -> dict[str, dict[str, Any]]:
    if not COOLDOWN_REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(COOLDOWN_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(data: dict[str, dict[str, Any]]) -> None:
    COOLDOWN_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOLDOWN_REGISTRY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def merge_registries(
    local: dict[str, dict[str, Any]], remote: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Merge two registries using 'latest wins' based on updated_at."""
    merged = local.copy()
    for email, remote_entry in remote.items():
        if email not in merged:
            merged[email] = remote_entry
        else:
            local_entry = merged[email]
            local_updated = local_entry.get("updated_at", "1970-01-01T00:00:00Z")
            remote_updated = remote_entry.get("updated_at", "1970-01-01T00:00:00Z")
            if remote_updated > local_updated:
                merged[email] = remote_entry
    return merged


def sync_registry_with_cloud(cp: B2Provider, dry_run: bool = False) -> None:
    """Download remote registry, merge with local, and upload the result."""
    from .ui import console

    remote_path = "cooldown.json"
    local_data = load_registry()

    # 1. Check if remote exists and merge if so
    files = cp.list_files(prefix=remote_path)
    remote_exists = any(f.name == remote_path for f in files)

    if remote_exists:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "remote_cooldown.json"
            try:
                cp.download_file(remote_path, tmp_path)
                remote_data = json.loads(tmp_path.read_text(encoding="utf-8"))
                local_data = merge_registries(local_data, remote_data)
                if not dry_run:
                    save_registry(local_data)
                else:
                    console.print("Would merge cloud registry with local registry")
            except Exception as exc:
                console.print(f"[yellow]Warning:[/] Failed to merge cloud registry: {exc}")

    # 2. Upload the updated/merged local registry back to cloud
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "cooldown.json"
        tmp_path.write_text(json.dumps(local_data, indent=2), encoding="utf-8")
        try:
            if not dry_run:
                cp.upload_file(tmp_path, remote_path)
                console.print("[green]Cloud registry synchronized.[/]")
            else:
                console.print(f"Would upload registry to cloud: {remote_path}")
        except Exception as exc:
            console.print(f"[yellow]Warning:[/] Failed to upload registry to cloud: {exc}")


def update_registry_entry(
    email: str,
    *,
    reset_at: datetime | str | None = None,
    is_expired: bool | None = None,
    quota_text: str | None = None,
    quota_percent_left: int | None = None,
    session_start_at: datetime | str | None = None,
    dry_run: bool = False,
) -> None:
    registry = load_registry()
    entry = registry.get(email, {})

    if reset_at:
        entry["reset_at"] = reset_at.isoformat() if hasattr(reset_at, "isoformat") else str(reset_at)
    if is_expired is not None:
        entry["is_expired"] = is_expired
    if quota_text:
        entry["quota_text"] = quota_text
    if quota_percent_left is not None:
        entry["quota_percent_left"] = quota_percent_left
    if session_start_at:
        entry["session_start_at"] = (
            session_start_at.isoformat() if hasattr(session_start_at, "isoformat") else str(session_start_at)
        )
    
    entry["updated_at"] = datetime.now().astimezone().isoformat()
    registry[email] = entry
    if not dry_run:
        save_registry(registry)
    else:
        from .ui import console
        console.print(f"Would update registry entry for {email}")


def get_registry_entry(email: str) -> dict[str, Any] | None:
    return load_registry().get(email)
