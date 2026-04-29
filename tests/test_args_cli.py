import argparse
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

from codex_manager.args import get_parser
from codex_manager.cli import main


def test_args_parser():
    parser = get_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    args = parser.parse_args(["backup", "--dry-run"])
    assert args.command == "backup"
    assert args.dry_run is True

def test_main_no_args():
    with patch.object(sys, 'argv', ['codex-manager']):
        try:
            main()
        except SystemExit as exc:
            assert exc.code != 0

def test_main_doctor(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'doctor'])
    with patch('codex_manager.cli.run_doctor') as mock_run_doctor:
        main()
        mock_run_doctor.assert_called_once()

def test_main_backup(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'backup'])
    with patch('codex_manager.cli.perform_backup') as mock_perform_backup:
        mock_perform_backup.return_value = (MagicMock(), MagicMock(), {"email": "a", "session_start_at": "b", "reset_at": "c", "quota_text": "d"})
        main()
        mock_perform_backup.assert_called_once()

def test_main_list_backups(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'list-backups'])
    with patch('codex_manager.cli.list_backups') as _mock:
        _mock.return_value = []
        main()

def test_main_restore(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'restore'])
    with patch('codex_manager.cli.perform_restore') as _mock:
        with patch('codex_manager.cli.sync_current_account_status') as _mock_sync:
            _mock.return_value = (MagicMock(), MagicMock(), {"email": "a", "session_start_at": "b", "reset_at": "c", "quota_text": "d"}, None)
            main()
            _mock_sync.assert_called_once()

def test_main_prune_backups(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'prune-backups'])
    with patch('codex_manager.cli.perform_prune_backups') as _mock:
        _mock.return_value = [MagicMock()]
        main()

def test_main_prune(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'prune'])
    with patch('codex_manager.cli.perform_prune') as _mock:
        plan = MagicMock()
        plan.files = []
        _mock.return_value = plan
        main()

def test_main_use(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'use'])
    with patch('codex_manager.cli.perform_use') as _mock:
        with patch('codex_manager.cli.sync_current_account_status') as _mock_sync:
            _mock.return_value = (MagicMock(), MagicMock(), {"email": "a", "session_start_at": "b", "reset_at": "c", "quota_text": "d"}, None, False)
            main()
            _mock_sync.assert_called_once()

def test_main_sync(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'sync', 'push', '--bucket-name', 'a'])
    with patch('codex_manager.cli.push_backup') as _mock:
        main()

def test_main_status(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'status'])
    with patch('codex_manager.cli.capture_tmux_status_text') as mock_read:
        with patch('codex_manager.cli.parse_live_status_text') as mock_parse:
            mock_read.return_value = "text"
            status = MagicMock()
            status.email = "test"
            status.session_start_at = datetime.now()
            status.reset_at = datetime.now()
            status.quota_percent_left = 0
            status.quota_text = "c"
            status.proposed_archive_name = "d"
            mock_parse.return_value = status
            with patch('codex_manager.backup.read_status_text_from_args') as mock_read_status:
                mock_read_status.return_value = "status"
                with patch('codex_manager.cli.patch_metadata') as mock_patch:
                    with patch('sys.stdin.isatty', return_value=True):
                        main()
                        mock_patch.assert_called_once()

def test_main_profile(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'profile', 'export', 'foo.tar.gz'])
    with patch('codex_manager.cli.export_profile') as _mock:
        main()

def test_main_recommend(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'recommend'])
    with patch('codex_manager.cli.list_backups') as _mock:
        from codex_manager.list_backups import BackupEntry
        entry = BackupEntry(
            archive_path=MagicMock(),
            email="test",
            session_start_at="2026-04-19T10:02:00+00:00",
            reset_at="2026-04-26T10:02:00+00:00",
            created_at="2026-04-20T10:02:00+00:00",
            quota_text="q",
            quota_percent_left=0
        )
        _mock.return_value = [entry]
        with patch('codex_manager.cli.choose_best_account') as mock_choose:
            recommendation = MagicMock()
            recommendation.selected.remaining_seconds = 0
            mock_choose.return_value = recommendation
            main()

def test_main_recommend_use(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'recommend', '--use'])
    with patch('codex_manager.cli.list_backups') as _mock:
        from codex_manager.list_backups import BackupEntry
        entry = BackupEntry(
            archive_path=MagicMock(),
            email="test",
            session_start_at="2026-04-19T10:02:00+00:00",
            reset_at="2026-04-26T10:02:00+00:00",
            created_at="2026-04-20T10:02:00+00:00",
            quota_text="q",
            quota_percent_left=0
        )
        _mock.return_value = [entry]
        with patch('codex_manager.cli.choose_best_account') as mock_choose:
            recommendation = MagicMock()
            recommendation.selected.email = "test@example.com"
            recommendation.selected.status = "ready"
            recommendation.selected.remaining_seconds = 0
            recommendation.selected.next_available_at.strftime.return_value = "2026-04-29 00:00:00 +0000"
            recommendation.selected.validation_status = "backup"
            recommendation.reason = "ready now"
            mock_choose.return_value = recommendation
            with patch('codex_manager.cli.handle_use') as mock_handle_use:
                main()
                mock_handle_use.assert_called_once()

def test_main_cooldown(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-manager', 'cooldown'])
    with patch('codex_manager.cli.list_backups') as _mock:
        from codex_manager.list_backups import BackupEntry
        entry = BackupEntry(
            archive_path=MagicMock(),
            email="test",
            session_start_at="2026-04-19T10:02:00+00:00",
            reset_at="2026-04-26T10:02:00+00:00",
            created_at="2026-04-20T10:02:00+00:00",
            quota_text="q",
            quota_percent_left=0
        )
        _mock.return_value = [entry]
        with patch('codex_manager.cli.evaluate_records') as mock_eval:
            mock_eval.return_value = []
            main()
