from __future__ import annotations

import builtins
import io
import sys
from importlib import reload
from unittest import mock

import pytest


def test_ui_rich_available(capsys):
    import codex_manager.ui as ui
    reload(ui)

    ui.console.print("Hello rich")
    captured = capsys.readouterr()
    assert "Hello rich" in captured.out

    ui.console.print("Error rich", stderr=True)
    captured = capsys.readouterr()
    assert "Error rich" in captured.err

    # Test status context manager
    with ui.console.status("Working"):
        pass


def test_ui_rich_fallback(monkeypatch, capsys):
    original_import = builtins.__import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rich.console":
            raise ImportError("Mocked ImportError for rich")
        return original_import(name, globals, locals, fromlist, level)

    with mock.patch("builtins.__import__", side_effect=mock_import):
        import codex_manager.ui as ui_fallback
        reload(ui_fallback)

    ui_fallback.console.print("Hello fallback")
    captured = capsys.readouterr()
    assert "Hello fallback" in captured.out

    ui_fallback.console.print("Error fallback", stderr=True)
    captured = capsys.readouterr()
    assert "Error fallback" in captured.err

    with ui_fallback.console.status("Working") as st:
        st.update("Still working")

    captured = capsys.readouterr()
    assert "Working ..." in captured.out
    assert "Still working ..." in captured.out

    # Test fallback table rendering
    table = ui_fallback.Table(show_header=True)
    table.add_column("Col1", justify="left")
    table.add_column("Col2", justify="center")
    table.add_column("Col3", justify="right")
    table.add_row("Value1", "Value2", "Value3")

    ui_fallback.console.print(table)
    captured = capsys.readouterr()
    out = captured.out
    assert "Col1" in out
    assert "Col2" in out
    assert "Col3" in out
    assert "Value1" in out
    assert "Value2" in out
    assert "Value3" in out

    # Test Panel
    panel = ui_fallback.Panel(table, title="[bold]Test Panel[/]")
    ui_fallback.console.print(panel)
    captured = capsys.readouterr()
    assert "--- Test Panel ---" in captured.out
    assert "Col1" in captured.out

    # Test clean tags
    ui_fallback.console.print("[bold red]Clean[/] me")
    captured = capsys.readouterr()
    assert "Clean me" in captured.out or "Clean[/] me" in captured.out

    # Restore module state
    import codex_manager.ui as ui
    reload(ui)
