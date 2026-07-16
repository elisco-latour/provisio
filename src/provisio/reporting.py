"""Console UX — the human-facing event stream, decoupled from rich.

`Reporter` is intentionally separate from the audit log (see logging.py): the
audit log is the complete, structured compliance record; the reporter is
best-effort, pretty, and safe to swap out (or silence with `NullReporter`).

Steps and primitives announce *events* through a `Reporter`; they never touch a
terminal or `rich` directly, so the same domain code runs under a recording
reporter in tests, a null reporter as a library, or the rich console in the CLI.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from provisio.errors import ProvisioError

if TYPE_CHECKING:
    from rich.console import Console


@runtime_checkable
class Reporter(Protocol):
    """Receives human-facing progress events.

    `step` marks the start of the n-th of `total` steps; the rest are one-line
    status messages under the current step.
    """

    def step(self, index: int, total: int, title: str) -> None: ...
    def ok(self, message: str) -> None: ...
    def skip(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


class NullReporter:
    """A reporter that does nothing — the quiet default for library use."""

    def step(self, index: int, total: int, title: str) -> None: ...
    def ok(self, message: str) -> None: ...
    def skip(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


class ConsoleReporter:
    """Renders events to a terminal with `rich`.

    `rich` is an optional extra, so it is imported lazily here: importing
    `provisio.reporting` never requires it, and only constructing a
    `ConsoleReporter` does.
    """

    def __init__(self, console: Console | None = None) -> None:
        if console is None:
            try:
                from rich.console import Console as RichConsole
            except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without the extra
                raise ProvisioError(
                    "ConsoleReporter needs the 'rich' extra. Install: pip install 'provisio[rich]'"
                ) from exc
            console = RichConsole()
        self._console = console

    # ASCII-safe status markers (colour via rich). We deliberately avoid glyphs
    # like ✓/→/⚠: rich downgrades box/rule characters on a legacy Windows (cp1252)
    # console, but NOT arbitrary glyphs, which raise UnicodeEncodeError there.
    # Words + colour are robust everywhere and still readable.
    def step(self, index: int, total: int, title: str) -> None:
        self._console.rule(f"[bold cyan]\\[{index}/{total}] {title}[/bold cyan]")

    def ok(self, message: str) -> None:
        self._console.print(f"  [green]OK[/green]   {message}")

    def skip(self, message: str) -> None:
        self._console.print(f"  [dim]SKIP {message}[/dim]")

    def warn(self, message: str) -> None:
        self._console.print(f"  [yellow]WARN[/yellow] {message}")

    def info(self, message: str) -> None:
        self._console.print(f"  {message}")

    def error(self, message: str) -> None:
        self._console.print(f"  [red]FAIL[/red] {message}")
