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


def identify_auth_email(auth_path: Path) -> str | None:
    from .utils import extract_email_from_auth_json
    return extract_email_from_auth_json(auth_path)


def resolve_named_archive(target: str, backup_dir: Path) -> Path:
    candidate = Path(target).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        return candidate

    # Try direct backup_dir / target
    archive_path = backup_dir / target
    if archive_path.exists():
        return archive_path

    # Try auth/<target>/latest.tar.gz
    if "@" in target:
        auth_path = backup_dir / "auth" / target / "latest.tar.gz"
        if auth_path.exists():
            return auth_path

    # Try subdirectories
    for sub in ("auth", "sessions"):
        p = backup_dir / sub / target
        if p.exists():
            return p
        # Check target without suffix or in subfolder
        p2 = backup_dir / sub / target / "latest.tar.gz"
        if p2.exists():
            return p2
        # Recursive glob search for target file inside subfolders of the subdirectory
        for cand in (backup_dir / sub).glob(f"**/{target}"):
            if cand.exists():
                return cand

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
        # Check new auth store location first
        archive_path = backup_dir / "auth" / args.email / "latest.tar.gz"
        if not archive_path.exists():
            archive_path = backup_dir / f"{args.email}-latest-codex.tar.gz"
            if not archive_path.exists():
                # Fallback: Find latest matching archive for this email
                try:
                    archive_path = latest_backup_archive(backup_dir, email=args.email)
                except FileNotFoundError as exc:
                    new_meta = backup_dir / "auth" / args.email / "latest.metadata.json"
                    legacy_meta = list(backup_dir.glob(f"*-{args.email}-codex.metadata.json"))
                    if new_meta.exists() or legacy_meta:
                        raise FileNotFoundError(
                            f"Cannot use account '{args.email}': Only metadata exists (no backup archive). "
                            "The account may have been pruned or saved as metadata-only."
                        ) from exc
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
    
    if email:
        auth_path = backup_dir / "auth" / email / "latest.tar.gz"
        if auth_path.exists():
            return auth_path
        
        # Fallback to legacy
        pattern = f"*-{email}-codex.tar.gz"
        archives = sorted(
            [p for p in backup_dir.glob(pattern) if "-latest-" not in p.name],
            key=lambda path: path.name,
            reverse=True,
        )
        if archives:
            return archives[0]
            
        raise FileNotFoundError(f"No Codex backup archives found for email {email} in: {backup_dir}")
    
    # No email: look in sessions/ and legacy
    sessions_dir = backup_dir / "sessions"
    candidates = []
    if sessions_dir.exists():
        candidates.extend(sessions_dir.glob("**/*.tar.gz"))
    candidates.extend([p for p in backup_dir.glob("*-codex.tar.gz") if "-latest-" not in p.name])
    
    if not candidates:
        raise FileNotFoundError(f"No Codex backup archives found in: {backup_dir}")
        
    candidates.sort(key=lambda p: p.name, reverse=True)
    return candidates[0]


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
            except KeyError:
                # Session backups might have different metadata file name, let's try getting the only metadata file
                metadata_members = [m for m in tar.getmembers() if m.name.endswith(".metadata.json")]
                if metadata_members:
                    member = metadata_members[0]
                else:
                    raise FileNotFoundError(
                        f"Metadata file not found beside archive or inside archive: {member_name}"
                    )
            extracted = tar.extractfile(member)
            if extracted is None:
                raise FileNotFoundError(f"Failed to extract metadata member: {member_name}")
            return json.loads(extracted.read().decode("utf-8"))
    except (zlib.error, tarfile.TarError) as exc:
        raise RuntimeError(f"Could not read metadata from archive (possibly corrupted): {exc}") from exc


def validate_archive_contents(archive_path: Path) -> None:
    # Under Separate Stores, session-only backups do not have auth.json
    try:
        metadata = load_metadata_for_archive(archive_path)
        if metadata.get("backup_mode") == "session-only" or "sessions/" in str(archive_path) or archive_path.name.startswith("backup-"):
            return  # Valid session-only backup (does not require auth.json)
    except Exception:
        pass

    with tarfile.open(archive_path, "r:gz") as tar:
        names = set(tar.getnames())
    if "auth.json" not in names:
        raise ValueError(f"Archive does not contain auth.json: {archive_path}")


def extract_archive_to_temp(archive_path: Path) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="codex-manager-restore-"))
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(temp_dir, filter="data")
    return temp_dir





def install_restored_tree(extracted_dir: Path, dest_dir: Path) -> None:
    # We move each item from the temporary extraction point to the final destination.
    # To prevent bind-mount issues or overlayfs locking errors on the root dest_dir,
    # we clear and populate the directory contents rather than deleting/replacing
    # the dest_dir folder itself.
    dest_dir.mkdir(parents=True, exist_ok=True)
    for child in dest_dir.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except Exception:
            pass

    for child in extracted_dir.iterdir():
        dest_child = dest_dir / child.name
        shutil.move(str(child), str(dest_child))

    try:
        shutil.rmtree(extracted_dir)
    except Exception:
        pass


def prune_metadata_file(extracted_dir: Path) -> None:
    for path in extracted_dir.glob("*.metadata.json"):
        path.unlink()


def perform_restore(args) -> tuple[Path, Path, dict, Path | None]:
    archive_path = resolve_archive_path(args)
    metadata = load_metadata_for_archive(archive_path)
    validate_archive_contents(archive_path)

    # To prevent safety backup auto-pruning from deleting our target archive
    # (which occurs when active_email == target_email), we copy the target archive
    # to a secure temporary location first before doing any safety backups.
    restore_source_path = archive_path
    temp_archive_dir = None
    if not getattr(args, "dry_run", False):
        temp_archive_dir = Path(tempfile.mkdtemp(prefix="codex-manager-restore-target-"))
        restore_source_path = temp_archive_dir / archive_path.name
        shutil.copy2(archive_path, restore_source_path)

    dest_dir = Path(args.dest_dir).expanduser()
    
    # Auto-backup active account before restore/switch to secure latest rotated refresh tokens.
    auth_path = dest_dir / "auth.json"
    auto_backup_path = None
    if auth_path.exists() and not getattr(args, "dry_run", False):
        active_email = identify_auth_email(auth_path)
        if active_email and active_email != "unknown":
            from .backup import perform_backup
            from types import SimpleNamespace
            
            backup_args = SimpleNamespace(
                source_dir=str(dest_dir),
                backup_dir=getattr(args, "backup_dir", str(CODEX_MANAGER_HOME / "backups")),
                status_file=None,
                status_command=None,
                reference_year=getattr(args, "reference_year", None),
                codex_command=getattr(args, "codex_command", "codex --no-alt-screen"),
                tmux_session_name=getattr(args, "tmux_session_name", None),
                tmux_cols=getattr(args, "tmux_cols", 120),
                tmux_rows=getattr(args, "tmux_rows", 40),
                startup_timeout_seconds=getattr(args, "startup_timeout_seconds", 20.0),
                status_timeout_seconds=getattr(args, "status_timeout_seconds", 20.0),
                include_tmp=False,
                dry_run=False,
                force=True,
                auth_only=True,  # Strictly auth-only auto backup
                prune_first=False,
                without_status_check=getattr(args, "status_confirmed_expired", False),
                captured_status_text=getattr(args, "captured_status_text", None),
            )
            try:
                auto_backup_path, _, _ = perform_backup(backup_args)
                from .ui import console
                console.print(f"[green]Auto-saved current active session for:[/] {active_email}")
            except Exception:
                # Fail-silent to ensure user's requested restore command is not blocked
                pass

    is_session = (
        metadata.get("backup_mode") == "session-only" 
        or "sessions/" in str(archive_path) 
        or archive_path.name.startswith("backup-")
    )
    is_auth_only = (
        getattr(args, "auth_only", False) 
        or "auth/" in str(archive_path) 
        or "latest-auth" in archive_path.name 
        or archive_path.name == "latest.tar.gz"
    )

    if is_session:
        if args.dry_run:
            return archive_path, dest_dir, metadata, None
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        from .backup import is_auth_file
        with tarfile.open(restore_source_path, "r:gz") as tar:
            for member in tar.getmembers():
                if not is_auth_file(member.name) and member.name != "latest.metadata.json" and not member.name.endswith(".metadata.json"):
                    tar.extract(member, path=dest_dir, filter="data")
        
        if temp_archive_dir:
            shutil.rmtree(temp_archive_dir)

        return archive_path, dest_dir, metadata, auto_backup_path

    elif is_auth_only:
        if args.dry_run:
            return archive_path, dest_dir, metadata, None
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        from .backup import is_auth_file
        with tarfile.open(restore_source_path, "r:gz") as tar:
            for member in tar.getmembers():
                if is_auth_file(member.name):
                    tar.extract(member, path=dest_dir, filter="data")
        
        if temp_archive_dir:
            shutil.rmtree(temp_archive_dir)

        email = metadata.get("email")
        if email and email != "unknown":
            set_active_account(email, dry_run=args.dry_run)
            
        return archive_path, dest_dir, metadata, auto_backup_path

    else:
        # Legacy Full Restore
        extracted_dir = extract_archive_to_temp(restore_source_path)
        prune_metadata_file(extracted_dir)

        if temp_archive_dir:
            shutil.rmtree(temp_archive_dir)

        if args.dry_run:
            shutil.rmtree(extracted_dir)
            return archive_path, dest_dir, metadata, None

        if dest_dir.exists():
            if not dest_dir.is_dir():
                dest_dir.unlink()

        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        install_restored_tree(extracted_dir, dest_dir)
        
        email = metadata.get("email")
        if email and email != "unknown":
            set_active_account(email, dry_run=args.dry_run)
            
        return archive_path, dest_dir, metadata, auto_backup_path


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
