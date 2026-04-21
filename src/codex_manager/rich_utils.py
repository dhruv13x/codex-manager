from __future__ import annotations

import re
import sys
from typing import Any, Iterable, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
    from rich.theme import Theme
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

def strip_rich_tags(text: str) -> str:
    """Removes Rich-style tags like [bold green]...[/] from text."""
    return re.sub(r"\[\/?[a-zA-Z ]+\]", "", text).replace("[/]", "")

class FallbackConsole:
    def __init__(self, stderr: bool = False):
        self.file = sys.stderr if stderr else sys.stdout

    def print(self, *args, **kwargs):
        if "style" in kwargs:
            kwargs.pop("style")

        # Override file if provided in kwargs
        file = kwargs.pop("file", self.file)

        processed_args = []
        for arg in args:
            if isinstance(arg, str):
                processed_args.append(strip_rich_tags(arg))
            elif hasattr(arg, "__str__"):
                processed_args.append(strip_rich_tags(str(arg)))
            else:
                processed_args.append(arg)

        print(*processed_args, file=file, **kwargs)

    def status(self, status, **kwargs):
        self.print(f"[*] {status}")
        class DummyStatus:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def update(self, status_msg, **update_kwargs):
                if status_msg:
                    print(f"[*] {strip_rich_tags(status_msg)}", file=sys.stdout)
        return DummyStatus()

if RICH_AVAILABLE:
    theme = Theme({
        "info": "dim cyan",
        "warning": "magenta",
        "danger": "bold red",
        "success": "bold green",
        "ready": "bold green",
        "cooldown": "bold yellow",
    })
    console = Console(theme=theme)
    error_console = Console(theme=theme, stderr=True)
else:
    console = FallbackConsole()
    error_console = FallbackConsole(stderr=True)

def create_table(
    title: Optional[str] = None,
    headers: Optional[list[str]] = None,
    rows: Optional[Iterable[Iterable[Any]]] = None,
    header_style: str = "bold magenta"
) -> Any:
    if RICH_AVAILABLE:
        table = Table(title=title, box=box.ROUNDED)
        if headers:
            for header in headers:
                table.add_column(header, header_style=header_style)
        if rows:
            for row in rows:
                table.add_row(*[str(item) for item in row])
        return table
    else:
        lines = []
        if title:
            lines.append(f"=== {title} ===")

        if not headers:
            if rows:
                for row in rows:
                    lines.append("  ".join(strip_rich_tags(str(item)) for item in row))
            return "\n".join(lines)

        clean_headers = [strip_rich_tags(h) for h in headers]
        clean_rows = [[strip_rich_tags(str(item)) for item in row] for row in (rows or [])]

        widths = [len(h) for h in clean_headers]
        for row in clean_rows:
            for i, item in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(item))
                else:
                    widths.append(len(item))

        header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(clean_headers))
        lines.append(header_line)
        lines.append("  ".join("-" * w for w in widths))

        for row in clean_rows:
            lines.append("  ".join(item.ljust(widths[i]) for i, item in enumerate(row)))

        return "\n".join(lines)

def get_status_style(status: str) -> str:
    status = status.lower()
    if status == "ready":
        return "success"
    if status == "cooldown":
        return "warning"
    return ""
