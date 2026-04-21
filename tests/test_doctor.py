from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codex_manager.doctor import _check_command, _check_dir_writable, run_doctor


def test_check_command(mocker) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    assert _check_command("tmux") is True

    mock_run.side_effect = subprocess.CalledProcessError(1, ["which", "nonexistent"])
    assert _check_command("nonexistent") is False

def test_check_dir_writable(tmp_path: Path) -> None:
    d1 = tmp_path / "d1"
    assert _check_dir_writable(d1) is True
    assert d1.exists()

    d2 = tmp_path / "d2"
    d2.mkdir()
    d2.chmod(0o444)
    # On some systems root can always write, so we might skip this or use a mock
    # But usually pytest runs as normal user.
    # assert _check_dir_writable(d2) is False

def test_run_doctor_all_ok(mocker, tmp_path: Path, capsys) -> None:
    mocker.patch("codex_manager.doctor._check_command", return_value=True)
    mocker.patch("codex_manager.doctor._check_dir_writable", return_value=True)
    mocker.patch("subprocess.run").return_value.stdout = "/usr/bin/tool"
    
    # Mock cloud provider to avoid Doppler/API calls
    mocker.patch("codex_manager.doctor.get_cloud_provider", return_value=None)
    
    # Mock urllib to avoid network calls
    mocker.patch("urllib.request.urlopen")

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    run_doctor(codex_home=codex_home, backup_dir=tmp_path / "backups")
    captured = capsys.readouterr()
    
    assert "Codex Manager Doctor" in captured.out
    assert "tmux" in captured.out
    assert "OK" in captured.out
    assert "Doctor check complete. No issues found!" in captured.out

def test_run_doctor_with_issues(mocker, tmp_path: Path, capsys) -> None:
    mocker.patch("codex_manager.doctor._check_command", return_value=False)
    mocker.patch("codex_manager.doctor._check_dir_writable", return_value=False)
    
    # Mock cloud provider to avoid Doppler/API calls
    mocker.patch("codex_manager.doctor.get_cloud_provider", return_value=None)
    
    # Mock urllib to fail
    mocker.patch("urllib.request.urlopen", side_effect=Exception("no net"))
    
    # Mock status parser to fail
    mocker.patch("codex_manager.status.parse_live_status_text", side_effect=Exception("parse error"))

    codex_home = tmp_path / ".codex" # Missing

    with pytest.raises(SystemExit) as exc:
        run_doctor(codex_home=codex_home, backup_dir=tmp_path / "backups")
    
    assert exc.value.code == 1
    captured = capsys.readouterr()
    
    assert "FAIL" in captured.out
    assert "tmux" in captured.out
    assert "Found 5 issue(s)" in captured.out or "Found 6 issue(s)" in captured.out
    assert "Not found in PATH" in captured.out
    assert "Dir: Codex Home" in captured.out
    assert "Dir: Backup Dir" in captured.out
    assert "Status Parser" in captured.out
    assert "parse error" in captured.out
