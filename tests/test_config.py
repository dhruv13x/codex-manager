from __future__ import annotations

import json
from pathlib import Path

from codex_manager.config import CODEX_MANAGER_HOME, load_config


def test_load_config_no_file(mocker, tmp_path: Path) -> None:
    mocker.patch("codex_manager.config.CODEX_MANAGER_HOME", tmp_path / "missing")
    config = load_config()
    assert config == {}


def test_load_config_valid_json(mocker, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    config_file = home / "config.json"
    config_file.write_text(json.dumps({"test_key": "test_value"}), encoding="utf-8")

    mocker.patch("codex_manager.config.CODEX_MANAGER_HOME", home)
    config = load_config()
    assert config == {"test_key": "test_value"}


def test_load_config_invalid_json(mocker, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    config_file = home / "config.json"
    config_file.write_text("invalid json", encoding="utf-8")

    mocker.patch("codex_manager.config.CODEX_MANAGER_HOME", home)
    config = load_config()
    assert config == {}
