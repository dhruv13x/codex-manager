from types import SimpleNamespace

import pytest

from codex_manager.args import get_parser
from codex_manager.cli import _apply_remove_target, _apply_restore_target
from codex_manager.restore import resolve_archive_path


def test_status_no_save_aliases_dry_run() -> None:
    args = get_parser().parse_args(["status", "--no-save"])
    assert args.command == "status"
    assert args.dry_run is True


def test_backup_no_status_aliases_without_status_check() -> None:
    args = get_parser().parse_args(["backup", "--no-status"])
    assert args.command == "backup"
    assert args.without_status_check is True


def test_use_target_accepts_email_or_backup_name() -> None:
    email_args = get_parser().parse_args(["use", "user@example.com"])
    _apply_restore_target(email_args)
    assert email_args.email == "user@example.com"
    assert email_args.from_archive is None

    archive_name = "2026-05-31-091200-user@example.com-codex.tar.gz"
    archive_args = get_parser().parse_args(["use", archive_name])
    _apply_restore_target(archive_args)
    assert archive_args.email is None
    assert archive_args.from_archive == archive_name





def test_resolve_archive_path_supports_backup_name_from_backup_dir(tmp_path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    archive_name = "2026-05-31-091200-user@example.com-codex.tar.gz"
    archive_path = backup_dir / archive_name
    archive_path.write_text("x", encoding="utf-8")

    args = SimpleNamespace(from_archive=archive_name, backup_dir=str(backup_dir), email=None)

    assert resolve_archive_path(args) == archive_path.resolve()


def test_resolve_archive_path_supports_metadata_name_from_backup_dir(tmp_path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    archive_name = "2026-05-31-091200-user@example.com-codex.tar.gz"
    archive_path = backup_dir / archive_name
    archive_path.write_text("x", encoding="utf-8")

    args = SimpleNamespace(
        from_archive=archive_name.replace(".tar.gz", ".metadata.json"),
        backup_dir=str(backup_dir),
        email=None,
    )

    assert resolve_archive_path(args) == archive_path.resolve()


def test_remove_accepts_positional_email() -> None:
    args = get_parser().parse_args(["remove", "user@example.com", "--yes"])
    _apply_remove_target(args)
    assert args.email == "user@example.com"


def test_remove_requires_email() -> None:
    args = get_parser().parse_args(["remove", "--yes"])
    with pytest.raises(SystemExit) as exc:
        _apply_remove_target(args)
    assert exc.value.code == 2
