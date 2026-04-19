from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from codex_manager.profile import export_profile, import_profile


def test_export_profile_no_home(mocker, tmp_path: Path) -> None:
    mocker.patch("codex_manager.profile.CODEX_MANAGER_HOME", tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        export_profile(tmp_path / "out.tar.gz")


def test_export_profile(mocker, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "test.json").write_text("{}", encoding="utf-8")

    mocker.patch("codex_manager.profile.CODEX_MANAGER_HOME", home)

    out_file = tmp_path / "export.tar.gz"
    export_profile(out_file)

    assert out_file.exists()
    with tarfile.open(out_file, "r:gz") as tar:
        assert "home" in tar.getnames()
        assert "home/test.json" in tar.getnames()


def test_import_profile_no_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        import_profile(tmp_path / "missing.tar.gz")


def test_import_profile(mocker, tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "old.json").write_text("{}", encoding="utf-8")

    mocker.patch("codex_manager.profile.CODEX_MANAGER_HOME", home)

    # Create dummy archive
    archive_dir = tmp_path / "archive_src"
    archive_home = archive_dir / "home"
    archive_home.mkdir(parents=True)
    (archive_home / "new.json").write_text("{}", encoding="utf-8")

    archive_path = tmp_path / "test.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        # cd to archive_dir effectively, so 'home' is the top level directory in tar
        tar.add(archive_home, arcname="home")

    import_profile(archive_path)

    # The existing home should be backed up
    backup_path = tmp_path / "home.bak"
    assert backup_path.exists()
    assert (backup_path / "old.json").exists()

    # The new home should have new.json
    assert home.exists()
    assert (home / "new.json").exists()

    captured = capsys.readouterr()
    assert "Backed up existing profile" in captured.out
