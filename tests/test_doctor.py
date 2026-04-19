from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codex_manager.doctor import _check_command, _check_dir_writable, run_doctor


def test_check_command(mocker) -> None:
    mock_run = mocker.patch("codex_manager.doctor.subprocess.run")

    mock_run.return_value = MagicMock()
    assert _check_command("tmux") is True

    mock_run.side_effect = subprocess.CalledProcessError(1, "which")
    assert _check_command("codex") is False


def test_check_dir_writable(tmp_path: Path) -> None:
    # Dir exists and writable
    d1 = tmp_path / "d1"
    d1.mkdir()
    assert _check_dir_writable(d1) is True

    # Dir doesn't exist, can be created
    d2 = tmp_path / "d2"
    assert _check_dir_writable(d2) is True
    assert d2.exists()


def test_run_doctor_all_ok(mocker, tmp_path: Path, capsys) -> None:
    mocker.patch("codex_manager.doctor._check_command", return_value=True)
    mocker.patch("codex_manager.doctor._check_dir_writable", return_value=True)
    mocker.patch("codex_manager.status.parse_live_status_text", return_value=None)

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    run_doctor(codex_home=codex_home, backup_dir=tmp_path / "backups")

    captured = capsys.readouterr()
    assert "Found 0 issue(s)" in captured.out


def test_run_doctor_with_issues(mocker, tmp_path: Path, capsys) -> None:
    mocker.patch("codex_manager.doctor._check_command", return_value=False)
    mocker.patch("codex_manager.doctor._check_dir_writable", return_value=False)
    mocker.patch("codex_manager.status.parse_live_status_text", side_effect=Exception("parse error"))

    codex_home = tmp_path / ".codex"

    with pytest.raises(SystemExit) as exc:
        run_doctor(codex_home=codex_home, backup_dir=tmp_path / "backups")

    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "Found 5 issue(s)" in captured.out
    assert "[FAIL] tmux is not found" in captured.out
    assert "[FAIL] codex is not found" in captured.out
    assert "[FAIL] Codex home" in captured.out
    assert "[FAIL] Backup directory" in captured.out
    assert "[FAIL] Status parser encountered an error" in captured.out
