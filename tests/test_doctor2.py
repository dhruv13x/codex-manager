from unittest.mock import MagicMock, patch

import pytest

from codex_manager.doctor import _check_dir_writable, run_doctor


def test_check_dir_writable_fail(tmp_path):
    with patch("codex_manager.doctor.Path.mkdir", side_effect=OSError):
        assert not _check_dir_writable(tmp_path / "missing")

@patch("codex_manager.doctor._check_command")
@patch("codex_manager.doctor._check_dir_writable")
@patch("codex_manager.doctor.subprocess.run")
@patch("codex_manager.doctor.get_cloud_provider")
@patch("codex_manager.doctor.urllib.request.urlopen")
def test_run_doctor_ok_with_cloud(mock_urlopen, mock_cp, mock_run, mock_writable, mock_cmd, tmp_path, capsys):
    mock_cmd.return_value = True
    mock_writable.return_value = True
    mock_run.return_value = MagicMock(stdout="path/to/cmd\n")

    cp_mock = MagicMock()
    cp_mock.bucket_name = "test_bucket"
    mock_cp.return_value = cp_mock

    with patch("codex_manager.status.parse_live_status_text"):
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()
        run_doctor(codex_home=codex_home, backup_dir=tmp_path / "backups")

        out = capsys.readouterr().out
        assert "Authenticated (Bucket: test_bucket)" in out
        assert "Doctor check complete. No issues found!" in out

@patch("codex_manager.doctor._check_command")
@patch("codex_manager.doctor._check_dir_writable")
@patch("codex_manager.doctor.get_cloud_provider")
@patch("codex_manager.doctor.urllib.request.urlopen")
def test_run_doctor_cloud_fail(mock_urlopen, mock_cp, mock_writable, mock_cmd, tmp_path, capsys):
    mock_cmd.return_value = True
    mock_writable.return_value = True

    mock_cp.side_effect = Exception("cloud error")

    with patch("codex_manager.status.parse_live_status_text"):
        codex_home = tmp_path / ".codex"
        codex_home.mkdir()

        with patch("codex_manager.doctor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="cmd")
            with pytest.raises(SystemExit):
                run_doctor(codex_home=codex_home, backup_dir=tmp_path / "backups")

        out = capsys.readouterr().out
        assert "cloud error" in out
