from pathlib import Path
from unittest.mock import MagicMock, patch

from codex_manager.prune_backups import perform_prune_backups


@patch("codex_manager.prune_backups.iter_backup_archives")
@patch("codex_manager.prune_backups.build_backup_entry")
def test_prune_backups_keep(mock_build, mock_iter):
    e1 = MagicMock(archive_path=Path("f1"), created_at="2026-04-20")
    e2 = MagicMock(archive_path=Path("f2"), created_at="2026-04-19")
    e3 = MagicMock(archive_path=Path("f3"), created_at="2026-04-18")

    mock_iter.return_value = [Path("f1"), Path("f2"), Path("f3")]
    mock_build.side_effect = [e1, e2, e3]

    with patch("codex_manager.restore.metadata_path_for_archive") as mock_meta:
        mock_meta.return_value = Path("meta")
        perform_prune_backups(Path("dir"), keep=1, keep_latest_per_email=False, dry_run=True)

@patch("codex_manager.prune_backups.iter_backup_archives")
@patch("codex_manager.prune_backups.build_backup_entry")
def test_prune_backups_keep_latest(mock_build, mock_iter):
    e1 = MagicMock(archive_path=Path("f1"), email="a", created_at="2026-04-20")
    e2 = MagicMock(archive_path=Path("f2"), email="a", created_at="2026-04-19")
    e3 = MagicMock(archive_path=Path("f3"), email="b", created_at="2026-04-18")

    mock_iter.return_value = [Path("f1"), Path("f2"), Path("f3")]
    mock_build.side_effect = [e1, e2, e3]

    with patch("codex_manager.restore.metadata_path_for_archive") as mock_meta:
        mock_meta.return_value = Path("meta")
        perform_prune_backups(Path("dir"), keep=None, keep_latest_per_email=True, dry_run=True)

@patch("codex_manager.prune_backups.iter_backup_archives")
@patch("codex_manager.prune_backups.build_backup_entry")
def test_prune_backups_actual_delete(mock_build, mock_iter):
    e1 = MagicMock(created_at="2026-04-20")
    e1.archive_path.name = "f1.tar.gz"
    meta_mock = MagicMock()
    meta_mock.exists.return_value = True
    e1.archive_path.with_name.return_value = meta_mock

    mock_iter.return_value = [Path("f1")]
    mock_build.side_effect = [e1]

    perform_prune_backups(Path("dir"), keep=0, keep_latest_per_email=False, dry_run=False)
    e1.archive_path.unlink.assert_called_once()
    meta_mock.unlink.assert_called_once()

def test_prune_backups_invalid_args():
    perform_prune_backups(Path("dir"), keep=None, keep_latest_per_email=False, dry_run=True)
