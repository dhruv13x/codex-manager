from unittest.mock import MagicMock, patch

import pytest

import codex_manager.cli as cli


@patch("codex_manager.cli.get_cloud_provider")
def test_ensure_cloud_archive(mock_cp):
    args = MagicMock()
    args.cloud = True
    args.from_archive = None
    args.email = "test"
    args.command = "use"

    cp = MagicMock()
    mock_cp.return_value = cp

    with patch("codex_manager.cli.list_cloud_backups") as mock_list:
        entry = MagicMock()
        entry.archive_path.name = "foo.tar.gz"
        mock_list.return_value = [entry]

        with patch("codex_manager.cli.tempfile.mkdtemp") as mock_tmp:
            mock_tmp.return_value = "/tmp/fake"
            cli._ensure_cloud_archive(args)
            cp.download_file.assert_called()

def test_ensure_cloud_archive_no_email():
    args = MagicMock()
    args.cloud = True
    args.from_archive = None
    args.email = None
    args.command = "restore"

    with patch("codex_manager.cli.get_cloud_provider") as mock_cp:
        mock_cp.return_value = MagicMock()
        with pytest.raises(SystemExit):
            cli._ensure_cloud_archive(args)

@patch("codex_manager.cli.get_cloud_provider")
def test_ensure_cloud_archive_recommend(mock_cp):
    args = MagicMock()
    args.cloud = True
    args.from_archive = None
    args.email = None
    args.command = "use"

    cp = MagicMock()
    mock_cp.return_value = cp

    with patch("codex_manager.cli.list_cloud_backups") as mock_list:
        entry = MagicMock()
        entry.archive_path.name = "foo.tar.gz"
        mock_list.return_value = [entry]

        with patch("codex_manager.cli.choose_best_account") as mock_choose:
            with patch("codex_manager.cli.evaluate_records") as mock_eval:
                rec = MagicMock()
                rec.selected.email = "rec_email"
                mock_choose.return_value = rec
                mock_eval.return_value = []

                with patch("codex_manager.cli.tempfile.mkdtemp") as mock_tmp:
                    mock_tmp.return_value = "/tmp/fake"
                    cli._ensure_cloud_archive(args)
                    assert args.email is None # at end it gets cleared
                    cp.download_file.assert_called()

@patch("codex_manager.cli.get_cloud_provider")
def test_ensure_cloud_archive_empty(mock_cp):
    args = MagicMock()
    args.cloud = True
    args.from_archive = None
    args.email = "a@b.com"

    cp = MagicMock()
    mock_cp.return_value = cp

    with patch("codex_manager.cli.list_cloud_backups") as mock_list:
        mock_list.return_value = []
        with pytest.raises(SystemExit):
            cli._ensure_cloud_archive(args)
