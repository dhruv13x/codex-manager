from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from .config import CODEX_MANAGER_HOME


def _safe_backup_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9@._-]+", "_", value).strip("._-") or "unknown"


def identify_auth_email(auth_path: Path) -> str | None:
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    email = data.get("email")
    return email if isinstance(email, str) and email.strip() else None


def resolve_archive_path(args) -> Path:
    if getattr(args, "from_archive", None):
        archive_path = Path(args.from_archive).expanduser()
    elif getattr(args, "email", None):
        archive_path = Path(args.backup_dir).expanduser() / f"{args.email}-latest-codex.tar.gz"
    else:
        archive_path = latest_backup_archive(Path(args.backup_dir).expanduser())

    if not archive_path.exists():
        raise FileNotFoundError(f"Backup archive does not exist: {archive_path}")
    return archive_path.resolve()


def latest_backup_archive(backup_dir: Path) -> Path:
    if not backup_dir.exists():
        raise FileNotFoundError(f"Backup directory does not exist: {backup_dir}")
    archives = sorted(
        backup_dir.glob("*-codex.tar.gz"),
        key=lambda path: path.name,
        reverse=True,
    )
    if not archives:
        raise FileNotFoundError(f"No Codex backup archives found in: {backup_dir}")
    return archives[0]


def metadata_path_for_archive(archive_path: Path) -> Path:
    return archive_path.with_name(archive_path.name.replace(".tar.gz", ".metadata.json"))


def load_metadata_for_archive(archive_path: Path) -> dict:
    metadata_path = metadata_path_for_archive(archive_path)
    if metadata_path.exists():
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    import zlib
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            member_name = archive_path.name.replace(".tar.gz", ".metadata.json")
            try:
                member = tar.getmember(member_name)
            except KeyError as exc:
                raise FileNotFoundError(
                    f"Metadata file not found beside archive or inside archive: {member_name}"
                ) from exc
            extracted = tar.extractfile(member)
            if extracted is None:
                raise FileNotFoundError(f"Failed to extract metadata member: {member_name}")
            return json.loads(extracted.read().decode("utf-8"))
    except (zlib.error, tarfile.TarError) as exc:
        raise RuntimeError(f"Could not read metadata from archive (possibly corrupted): {exc}") from exc


def validate_archive_contents(archive_path: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as tar:
        names = set(tar.getnames())
    if "auth.json" not in names:
        raise ValueError(f"Archive does not contain auth.json: {archive_path}")


def extract_archive_to_temp(archive_path: Path) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="codex-manager-restore-"))
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(temp_dir, filter="data")
    return temp_dir


def move_existing_target(dest_dir: Path) -> Path | None:
    if not dest_dir.exists():
        return None
    
    safety_dir = CODEX_MANAGER_HOME / "safety_backups"
    safety_dir.mkdir(parents=True, exist_ok=True)
    
    backup_path = safety_dir / f"{dest_dir.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.move(str(dest_dir), str(backup_path))
    return backup_path


def install_restored_tree(extracted_dir: Path, dest_dir: Path) -> None:
    # Use shutil.move because it handles cross-filesystem moves correctly.
    # We move the entire tree from the temporary extraction point to the final destination.
    if dest_dir.exists():
        if dest_dir.is_dir():
            shutil.rmtree(dest_dir)
        else:
            dest_dir.unlink()
    
    shutil.move(str(extracted_dir), str(dest_dir))


def prune_metadata_file(extracted_dir: Path) -> None:
    for path in extracted_dir.glob("*.metadata.json"):
        path.unlink()


def perform_restore(args) -> tuple[Path, Path, dict, Path | None]:
    archive_path = resolve_archive_path(args)
    metadata = load_metadata_for_archive(archive_path)
    validate_archive_contents(archive_path)

    dest_dir = Path(args.dest_dir).expanduser()
    
    auth_only = getattr(args, "auth_only", False)
    
    if auth_only:
        if args.dry_run:
            return archive_path, dest_dir, metadata, None
        
        # Ensure destination directory exists for auth-only extraction
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Swapping just auth-related files
        from .backup import AUTH_ONLY_INCLUDES
        
        # Backup auth.json if it exists
        auth_path = dest_dir / "auth.json"
        existing_backup_path = None
        if auth_path.exists():
            safety_dir = CODEX_MANAGER_HOME / "safety_backups"
            safety_dir.mkdir(parents=True, exist_ok=True)
            current_email = identify_auth_email(auth_path)
            email_label = _safe_backup_label(current_email) if current_email else "unknown"
            existing_backup_path = safety_dir / (
                f"auth.json.{email_label}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )
            shutil.copy2(auth_path, existing_backup_path)
        
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name in AUTH_ONLY_INCLUDES:
                    tar.extract(member, path=dest_dir, filter="data")
        return archive_path, dest_dir, metadata, existing_backup_path

    extracted_dir = extract_archive_to_temp(archive_path)
    prune_metadata_file(extracted_dir)

    existing_backup_path: Path | None = None
    if args.dry_run:
        shutil.rmtree(extracted_dir)
        return archive_path, dest_dir, metadata, existing_backup_path

    if dest_dir.exists() and not args.force:
        existing_backup_path = move_existing_target(dest_dir)
    elif dest_dir.exists() and args.force:
        shutil.rmtree(dest_dir)

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    install_restored_tree(extracted_dir, dest_dir)
    return archive_path, dest_dir, metadata, existing_backup_path


def restore_result_to_text(
    archive_path: Path,
    dest_dir: Path,
    metadata: dict,
    existing_backup_path: Path | None,
    *,
    dry_run: bool,
) -> str:
    lines = [
        f"mode: {'dry-run' if dry_run else 'restored'}",
        f"archive: {archive_path}",
        f"destination: {dest_dir}",
        f"email: {metadata.get('email', 'unknown')}",
        f"session_start_at: {metadata.get('session_start_at', 'unknown')}",
        f"reset_at: {metadata.get('reset_at', 'unknown')}",
        f"quota_text: {metadata.get('quota_text', 'unknown')}",
    ]
    if existing_backup_path is not None:
        lines.append(f"safety_backup: {existing_backup_path}")
    return "\n".join(lines)
