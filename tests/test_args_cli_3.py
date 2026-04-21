
import pytest

from codex_manager.args import RichHelpParser


def test_rich_help_parser_error(capsys):
    parser = RichHelpParser()
    with pytest.raises(SystemExit) as exc:
        parser.error("test error message")

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "Error:" in captured.err
    assert "test error message" in captured.err
