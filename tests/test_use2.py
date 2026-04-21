from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from codex_manager.use_account import perform_use, use_result_to_text


@patch("codex_manager.use_account.perform_restore")
@patch("codex_manager.use_account.choose_best_account")
@patch("codex_manager.use_account.evaluate_records")
@patch("codex_manager.cli.list_entries_from_args")
def test_perform_use_recommend(mock_list, mock_eval, mock_choose, mock_restore, tmp_path):
    mock_list.return_value = [MagicMock()]
    rec = MagicMock()
    rec.selected.email = "a@b.com"
    mock_choose.return_value = rec
    mock_restore.return_value = (Path("arc"), Path("dest"), {"email": "a@b.com"}, None)

    args = SimpleNamespace(email=None, from_archive=None, dest_dir=str(tmp_path / "dest"), clean=False, dry_run=False)
    arc, dest, meta, prev, pruned = perform_use(args)
    assert args.email == "a@b.com"

@patch("codex_manager.cli.list_entries_from_args")
def test_perform_use_recommend_fail(mock_list, tmp_path):
    mock_list.return_value = []
    args = SimpleNamespace(email=None, from_archive=None, dest_dir=str(tmp_path / "dest"))
    with pytest.raises(ValueError):
        perform_use(args)

@patch("codex_manager.use_account.perform_restore")
@patch("codex_manager.use_account.perform_prune")
def test_perform_use_clean_dry_run(mock_prune, mock_restore, tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    args = SimpleNamespace(email="test", from_archive=None, dest_dir=str(dest), clean=True, dry_run=True)
    mock_restore.return_value = (Path("arc"), dest, {"email": "test"}, None)

    arc, res_dest, meta, prev, pruned = perform_use(args)
    assert pruned is True
    mock_prune.assert_called_once()

def test_use_result_to_text():
    res = use_result_to_text(Path("arc"), Path("dest"), {"email": "test"}, Path("prev"), dry_run=True, pruned=True)
    try:
        import io

        from rich.console import Console
        console = Console(file=io.StringIO(), force_terminal=False)
        console.print(res)
        res_str = console.file.getvalue()
    except ImportError:
        res_str = str(res)
    assert "dry-run" in res_str
    assert "yes" in res_str
    assert "safety_backup" in res_str or "backed_up_existing_to" in res_str
