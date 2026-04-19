from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codex_manager.prune import build_prune_plan, perform_prune


def make_args(source_dir: Path, *, dry_run: bool):
    return SimpleNamespace(
        source_dir=str(source_dir),
        dry_run=dry_run,
    )


def test_build_prune_plan_matches_alias_targets(tmp_path: Path) -> None:
    (tmp_path / "state_5.sqlite").write_text("", encoding="utf-8")
    (tmp_path / "state_5.sqlite-shm").write_text("", encoding="utf-8")
    (tmp_path / "logs_2.sqlite").write_text("", encoding="utf-8")
    (tmp_path / "models_cache.json").write_text("", encoding="utf-8")
    (tmp_path / "history.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "cache").mkdir()
    (tmp_path / "sessions").mkdir()
    (tmp_path / "auth.json").write_text("{}", encoding="utf-8")

    plan = build_prune_plan(tmp_path)

    assert any(path.name == "state_5.sqlite" for path in plan.files)
    assert any(path.name == "state_5.sqlite-shm" for path in plan.files)
    assert any(path.name == "logs_2.sqlite" for path in plan.files)
    assert any(path.name == "models_cache.json" for path in plan.files)
    assert any(path.name == "history.jsonl" for path in plan.files)
    assert any(path.name == "cache" for path in plan.directories)
    assert any(path.name == "sessions" for path in plan.directories)
    assert not any(path.name == "auth.json" for path in plan.files)


def test_prune_dry_run_preserves_files(tmp_path: Path) -> None:
    (tmp_path / "state_5.sqlite").write_text("", encoding="utf-8")
    (tmp_path / "cache").mkdir()
    (tmp_path / "auth.json").write_text("{}", encoding="utf-8")

    perform_prune(make_args(tmp_path, dry_run=True))

    assert (tmp_path / "state_5.sqlite").exists()
    assert (tmp_path / "cache").exists()
    assert (tmp_path / "auth.json").exists()


def test_prune_removes_runtime_state_but_preserves_auth(tmp_path: Path) -> None:
    (tmp_path / "state_5.sqlite").write_text("", encoding="utf-8")
    (tmp_path / "history.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "cache").mkdir()
    (tmp_path / "sessions").mkdir()
    (tmp_path / "auth.json").write_text("{}", encoding="utf-8")
    (tmp_path / "config.toml").write_text("", encoding="utf-8")

    perform_prune(make_args(tmp_path, dry_run=False))

    assert not (tmp_path / "state_5.sqlite").exists()
    assert not (tmp_path / "history.jsonl").exists()
    assert not (tmp_path / "cache").exists()
    assert not (tmp_path / "sessions").exists()
    assert (tmp_path / "auth.json").exists()
    assert (tmp_path / "config.toml").exists()
