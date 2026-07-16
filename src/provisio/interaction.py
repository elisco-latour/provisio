"""Interaction ports: confirmation and input, decoupled from typer/TTY.

Moving these behind Protocols is what removes the last CLI-framework coupling
from the domain: a step calls ``ctx.confirm.confirm(...)`` and never touches
``typer.confirm``/``sys.stdin``. The CLI wires a real interactive implementation;
CI wires an `AutoConfirmer`; tests wire fakes.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Confirmer(Protocol):
    """Answers a yes/no confirmation."""

    def confirm(self, prompt: str, *, default: bool = False) -> bool: ...


@runtime_checkable
class Prompter(Protocol):
    """Asks for a single input value (optionally a secret)."""

    def ask(self, label: str, *, default: str | None = None, secret: bool = False) -> str | None: ...


class AutoConfirmer:
    """Answers every confirmation the same way without prompting.

    This is the CI / ``--yes`` path (answer=True) — and the sensible default for
    non-interactive use, matching the legacy CLI's behaviour of proceeding when
    there is no TTY.
    """

    def __init__(self, answer: bool = True) -> None:
        self._answer = answer

    def confirm(self, prompt: str, *, default: bool = False) -> bool:
        return self._answer
