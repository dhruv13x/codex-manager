import importlib
import sys


def test_console_print_style_stderr(monkeypatch, capsys):
    from codex_manager.ui import console
    console.print("test stderr", stderr=True, style="red")

    # Now let's try the fallback print by manually making console an instance of the fallback Console
    monkeypatch.setitem(sys.modules, 'rich.console', None)
    monkeypatch.setitem(sys.modules, 'rich.table', None)
    monkeypatch.setitem(sys.modules, 'rich.panel', None)
    monkeypatch.setitem(sys.modules, 'rich.status', None)
    monkeypatch.setitem(sys.modules, 'rich', None)
    import codex_manager.ui
    importlib.reload(codex_manager.ui)

    codex_manager.ui.console.print("test fallback stderr", stderr=True, style="red")
    codex_manager.ui.console.print("no markup test", markup=False)

    # Render table with justification types to get coverage
    t = codex_manager.ui.Table(show_header=True)
    t.add_column("Col1", justify="left")
    t.add_column("Col2", justify="center")
    t.add_column("Col3", justify="right")
    t.add_row("A", "B", "C")
    out = t.render()
    assert "Col1" in out

    monkeypatch.delitem(sys.modules, 'rich.console', raising=False)
    monkeypatch.delitem(sys.modules, 'rich.table', raising=False)
    monkeypatch.delitem(sys.modules, 'rich.panel', raising=False)
    monkeypatch.delitem(sys.modules, 'rich.status', raising=False)
    monkeypatch.delitem(sys.modules, 'rich', raising=False)
    importlib.reload(codex_manager.ui)
