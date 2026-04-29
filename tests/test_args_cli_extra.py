from unittest.mock import MagicMock

from codex_manager.cli import main


def test_main_use_cloud(mocker, monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["cm", "use", "--cloud", "--email", "test@example.com"])

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)

    mock_entry = MagicMock()
    mock_entry.archive_path.name = "test.tar.gz"

    mocker.patch("codex_manager.cli.list_cloud_backups", return_value=[mock_entry])
    mocker.patch("codex_manager.cli.tempfile.mkdtemp", return_value=str(tmp_path))

    mocker.patch("codex_manager.cli.sync_current_account_status")
    mocker.patch("codex_manager.cli.perform_use", return_value=(tmp_path / "test.tar.gz", tmp_path, {}, None, False))
    mocker.patch("codex_manager.cli.use_result_to_text", return_value="use result")

    main()

def test_main_restore_cloud(mocker, monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["cm", "restore", "--cloud", "--email", "test@example.com"])

    mock_cp = MagicMock()
    mocker.patch("codex_manager.cli.get_cloud_provider", return_value=mock_cp)

    mock_entry = MagicMock()
    mock_entry.archive_path.name = "test.tar.gz"

    mocker.patch("codex_manager.cli.list_cloud_backups", return_value=[mock_entry])
    mocker.patch("codex_manager.cli.tempfile.mkdtemp", return_value=str(tmp_path))

    mocker.patch("codex_manager.cli.sync_current_account_status")
    mocker.patch("codex_manager.cli.perform_restore", return_value=(tmp_path / "test.tar.gz", tmp_path, {}, None))
    mocker.patch("codex_manager.cli.restore_result_to_text", return_value="restore result")

    main()
