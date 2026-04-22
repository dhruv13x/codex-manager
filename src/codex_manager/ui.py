from __future__ import annotations

import re
import sys

try:
    from rich.console import Console as RichConsole
    from rich.panel import Panel
    from rich.status import Status
    from rich.table import Table
    from rich.prompt import Confirm

    class Console:
        def __init__(self):
            self._stdout_console = RichConsole()
            self._stderr_console = RichConsole(stderr=True)

        def print(self, *objects, stderr=False, **kwargs):
            if stderr:
                self._stderr_console.print(*objects, **kwargs)
            else:
                self._stdout_console.print(*objects, **kwargs)

        def status(self, status: str, **kwargs) -> Status:
            return self._stdout_console.status(status, **kwargs)

    console = Console()
except ImportError:

    class DummyStatus:
        def __init__(self, message: str):
            self.message = message

        def __enter__(self):
            print(f"{self.message}...")
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class Panel:
        def __init__(self, renderable, title=None, expand=True, **kwargs):
            self.renderable = renderable
            self.title = title

        def render(self) -> str:
            lines = []
            if self.title:
                lines.append(f"--- {self.title} ---")
            else:
                lines.append("-------------")

            # Very basic string conversion
            if hasattr(self.renderable, "render"):
                lines.append(self.renderable.render())
            else:
                lines.append(str(self.renderable))

            lines.append("-------------")
            return "\n".join(lines)

    class Table:
        def __init__(self, show_header=True, header_style=None):
            self.columns = []
            self.rows = []
            self.show_header = show_header

        def add_column(self, header, style=None, justify="left"):
            self.columns.append({"header": header, "justify": justify})

        def add_row(self, *row_data):
            self.rows.append([str(item) for item in row_data])

        def render(self) -> str:
            if not self.columns:
                return ""

            widths = [len(col["header"]) for col in self.columns]
            for row in self.rows:
                for idx, cell in enumerate(row):
                    clean_cell = re.sub(r'\[.*?\]', '', cell)
                    widths[idx] = max(widths[idx], len(clean_cell))

            def format_row(values) -> str:
                formatted = []
                for idx, val in enumerate(values):
                    clean_val = re.sub(r'\[.*?\]', '', str(val))
                    justify = self.columns[idx]["justify"]
                    if justify == "center":
                        formatted.append(clean_val.center(widths[idx]))
                    elif justify == "right":
                        formatted.append(clean_val.rjust(widths[idx]))
                    else:
                        formatted.append(clean_val.ljust(widths[idx]))
                return "  ".join(formatted)

            lines = []
            if self.show_header:
                headers = [col["header"] for col in self.columns]
                lines.append(format_row(headers))
                lines.append(format_row(["-" * width for width in widths]))

            for row in self.rows:
                lines.append(format_row(row))

            return "\n".join(lines)

    class Confirm:
        @staticmethod
        def ask(prompt: str, default: bool = False) -> bool:
            suffix = " (Y/n)" if default else " (y/N)"
            # Strip rich tags for plain input
            clean_prompt = re.sub(r'\[/?[a-zA-Z\s]+\]', '', prompt)
            try:
                result = input(f"{clean_prompt}{suffix}: ").strip().lower()
                if not result:
                    return default
                return result in ("y", "yes")
            except (EOFError, KeyboardInterrupt):
                return False


    class Console:
        def __init__(self):
            pass

        def status(self, status: str, **kwargs):
            return DummyStatus(re.sub(r'\[/?[a-zA-Z\s]+\]', '', status))

        def print(self, *objects, sep=" ", end="\n", file=None, style=None, stderr=False, markup=True, **kwargs):
            out_file = sys.stderr if stderr else (file or sys.stdout)

            clean_objects = []
            for obj in objects:
                if isinstance(obj, Table) or isinstance(obj, Panel):
                    clean_objects.append(obj.render())
                elif isinstance(obj, str):
                    if markup:
                        # Only strip rich tags, typically colored text like [bold red] or [/]
                        # Don't strip JSON arrays by restricting to alphabet and /
                        clean_objects.append(re.sub(r'\[/?[a-zA-Z\s]+\]', '', obj))
                    else:
                        clean_objects.append(obj)
                else:
                    clean_objects.append(str(obj))

            print(*clean_objects, sep=sep, end=end, file=out_file)

    console = Console()
