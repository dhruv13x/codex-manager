from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from .config import CODEX_MANAGER_HOME
from .registry import set_active_account


def _safe_backup_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9@._-]+", "_", value).strip("._-") or "unknown"


def identify_auth_email(auth_path: Path) -> str | None:
    from .utils import extract_email_from_auth_json
    return extract_email_from_auth_json(auth_path)


def resolve_named_archive(target: str, backup_dir: Path) -> Path:
    candidate = Path(target).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        return candidate

    archive_path = backup_dir / target
    if archive_path.exists():
        return archive_path

    safety_archive = CODEX_MANAGER_HOME / "safety_backups" / target
    if safety_archive.exists():
        return safety_archive

    metadata_name = target
    if metadata_name.endswith(".metadata.json"):
        archive_path = backup_dir / metadata_name.replace(".metadata.json", ".tar.gz")
        if archive_path.exists():
            return archive_path

    if target.endswith("-codex") and not target.endswith(".tar.gz"):
        archive_path = backup_dir / f"{target}.tar.gz"
        if archive_path.exists():
            return archive_path

    return backup_dir / target


def resolve_archive_path(args) -> Path:
    backup_dir = Path(getattr(args, "backup_dir", "~/.codex-manager/backups")).expanduser()
    target = getattr(args, "from_archive", None)
    if getattr(args, "from_archive", None):
        archive_path = resolve_named_archive(args.from_archive, backup_dir)
    elif getattr(args, "email", None):
        backup_dir = Path(args.backup_dir).expanduser()
        archive_path = backup_dir / f"{args.email}-latest-codex.tar.gz"
        if not archive_path.exists():
            # Fallback: Find latest matching archive for this email
            try:
                archive_path = latest_backup_archive(backup_dir, email=args.email)
            except FileNotFoundError as exc:
                if list(backup_dir.glob(f"*-{args.email}-codex.metadata.json")):
                    raise FileNotFoundError(
                        f"Cannot use account '{args.email}': Only metadata exists (no backup archive). "
                        "The account may have been pruned or saved as metadata-only."
                    ) from exc
                # Re-raise or let it fall through to the .exists() check below
                pass
    else:
        archive_path = latest_backup_archive(Path(args.backup_dir).expanduser())

    if not archive_path.exists():
        if target and Path(target).expanduser().parent == Path("."):
            raise FileNotFoundError(
                f"Backup target not found in {backup_dir}: {target}. Run cm list-backups."
            )
        raise FileNotFoundError(f"Backup archive does not exist: {archive_path}")
    return archive_path.resolve()


def latest_backup_archive(backup_dir: Path, email: str | None = None) -> Path:
    if not backup_dir.exists():
        raise FileNotFoundError(f"Backup directory does not exist: {backup_dir}")
    
    pattern = "*-codex.tar.gz"
    if email:
        pattern = f"*-{email}-codex.tar.gz"
        
    archives = sorted(
        [
            p for p in backup_dir.glob(pattern)
            if "-latest-" not in p.name
        ],
        key=lambda path: path.name,
        reverse=True,
    )
    
    if not archives:
        msg = f"No Codex backup archives found in: {backup_dir}"
        if email:
            msg = f"No Codex backup archives found for email {email} in: {backup_dir}"
        raise FileNotFoundError(msg)
    return archives[0]


def metadata_path_for_archive(archive_path: Path) -> Path:
    return archive_path.with_name(archive_path.name.replace(".tar.gz", ".metadata.json"))


def load_metadata_for_archive(archive_path: Path) -> dict:
    if ".bak-" in archive_path.name:
        email = "unknown"
        parts = archive_path.name.split(".bak-")
        if len(parts) == 2:
            prefix = parts[0]
            if prefix.startswith(".codex."):
                email = prefix[7:].strip(".")
            elif prefix.startswith("auth.json."):
                email = prefix[10:].strip(".")
                
        return {
            "email": email,
            "session_start_at": "unknown (safety backup)",
            "reset_at": "unknown (safety backup)",
            "quota_text": "Restored from safety backup",
        }

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

    auth_path = dest_dir / "auth.json"
    if not auth_path.exists():
        # If no auth credentials exist, it is a useless blank or purged state.
        # Clean it up directly instead of creating a redundant safety backup.
        if dest_dir.is_dir():
            shutil.rmtree(dest_dir)
        else:
            dest_dir.unlink()
        return None
    
    current_email = identify_auth_email(auth_path)
    if not current_email:
        from .registry import get_active_account
        current_email = get_active_account()

    email_label = f".{_safe_backup_label(current_email)}" if current_email else ""

    safety_dir = CODEX_MANAGER_HOME / "safety_backups"
    safety_dir.mkdir(parents=True, exist_ok=True)
    
    backup_path = safety_dir / f"{dest_dir.name}{email_label}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz"
    
    try:
        if dest_dir.is_dir():
            with tarfile.open(backup_path, "w:gz") as tar:
                for child in sorted(dest_dir.iterdir(), key=lambda item: item.name):
                    if child.name in {"tmp", ".tmp"}:
                        continue
                    tar.add(child, arcname=child.name)
            shutil.rmtree(dest_dir)
        else:
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(dest_dir, arcname=dest_dir.name)
            dest_dir.unlink()
    except Exception as exc:
        # Fallback safeguard: if compression fails, move the directory/file raw
        backup_path_fallback = safety_dir / f"{dest_dir.name}{email_label}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if backup_path.exists():
            backup_path.unlink()
        shutil.move(str(dest_dir), str(backup_path_fallback))
        return backup_path_fallback

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
            current_email = getattr(args, "current_account_email", None) or identify_auth_email(auth_path)
            email_label = _safe_backup_label(current_email) if current_email else "unknown"
            existing_backup_path = safety_dir / (
                f"auth.json.{email_label}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )
            shutil.copy2(auth_path, existing_backup_path)
        
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name in AUTH_ONLY_INCLUDES:
                    tar.extract(member, path=dest_dir, filter="data")
        
        email = metadata.get("email")
        if email:
            set_active_account(email, dry_run=args.dry_run)
            
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
    
    email = metadata.get("email")
    if email:
        set_active_account(email, dry_run=args.dry_run)
        
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
