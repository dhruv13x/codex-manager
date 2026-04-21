import importlib
import sys


def test_ui_fallback(monkeypatch, capsys):
    # Hide rich module to trigger ImportError fallback
    monkeypatch.setitem(sys.modules, 'rich.console', None)
    monkeypatch.setitem(sys.modules, 'rich.table', None)
    monkeypatch.setitem(sys.modules, 'rich.panel', None)
    monkeypatch.setitem(sys.modules, 'rich.status', None)
    monkeypatch.setitem(sys.modules, 'rich', None)

    # Reload codex_manager.ui to execute the fallback block
    import codex_manager.ui
    importlib.reload(codex_manager.ui)

    # Now we are using the fallback implementations
    from codex_manager.ui import Panel, Table, console

    # Test Panel
    p = Panel("hello", title="Test Panel")
    out = p.render()
    assert "--- Test Panel ---" in out
    assert "hello" in out

    # Test Panel without title
    p2 = Panel("world")
    assert "world" in p2.render()

    # Test Table
    t = Table(show_header=True)
    t.add_column("Col1", justify="left")
    t.add_column("Col2", justify="center")
    t.add_column("Col3", justify="right")
    t.add_row("A", "B", "C")
    out = t.render()
    assert "Col1" in out

    # Test Table without columns
    t2 = Table()
    assert t2.render() == ""

    # Test console print
    console.print(Panel("hello"))
    console.print(Table())
    console.print("[bold red]rich text[/bold red]")

    # Test console status
    with console.status("Testing"):
        pass

    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert "rich text" in captured.out
    assert "Testing" in captured.out

    # Restore module for other tests (pytest will revert monkeypatch automatically, but we need to reload ui)
    monkeypatch.delitem(sys.modules, 'rich.console', raising=False)
    monkeypatch.delitem(sys.modules, 'rich.table', raising=False)
    monkeypatch.delitem(sys.modules, 'rich.panel', raising=False)
    monkeypatch.delitem(sys.modules, 'rich.status', raising=False)
    monkeypatch.delitem(sys.modules, 'rich', raising=False)
    importlib.reload(codex_manager.ui)
