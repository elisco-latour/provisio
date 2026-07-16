"""Test doubles shipped *with* provisio.

Testability is a headline feature, so the fakes consumers need to test their own
infrastructure glue live in the public `provisio.testing` namespace rather than in
each project's test folder. They contain no cloud or subprocess knowledge.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace

from provisio.command import CommandResult
from provisio.errors import CommandFailedError


class FakeCommandRunner:
    """A `CommandRunner` that records argv and returns canned results.

    Register expectations with ``stub(*prefix, stdout=..., returncode=...)``: a
    call whose argv starts with a registered prefix returns that result (with its
    ``args`` set to the *actual* argv). Unmatched calls default to success with
    empty stdout. Inspect what ran via ``.calls`` and ``.issued(*prefix)``.

    Honours ``check`` exactly like the real runner, so idempotency tests can
    assert both the skip branch (probe returns success) and the create branch.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._rules: list[tuple[tuple[str, ...], CommandResult]] = []

    def stub(
        self,
        *prefix: str,
        stdout: str = "",
        returncode: int = 0,
        stderr: str = "",
    ) -> FakeCommandRunner:
        """Register a canned result for any call whose argv starts with ``prefix``.

        Returns self so stubs can be chained.
        """
        canned = CommandResult(args=prefix, returncode=returncode, stdout=stdout, stderr=stderr)
        self._rules.append((prefix, canned))
        return self

    def run(self, args: Sequence[str], *, check: bool = True) -> CommandResult:
        argv = tuple(args)
        self.calls.append(argv)
        result = replace(self._match(argv), args=argv)
        if check and not result.ok:
            raise CommandFailedError(result)
        return result

    def issued(self, *prefix: str) -> bool:
        """True if any recorded call's argv starts with ``prefix``."""
        return any(call[: len(prefix)] == prefix for call in self.calls)

    def _match(self, argv: tuple[str, ...]) -> CommandResult:
        for prefix, canned in self._rules:
            if argv[: len(prefix)] == prefix:
                return canned
        return CommandResult(args=argv, returncode=0)


class RecordingReporter:
    """A `Reporter` that records events as ``(level, message)`` tuples.

    Tests assert on ``.events`` (order + content) or ``.messages(level)``. For a
    ``step`` event the message is the step title.
    """

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def step(self, index: int, total: int, title: str) -> None:
        self.events.append(("step", title))

    def ok(self, message: str) -> None:
        self.events.append(("ok", message))

    def skip(self, message: str) -> None:
        self.events.append(("skip", message))

    def warn(self, message: str) -> None:
        self.events.append(("warn", message))

    def info(self, message: str) -> None:
        self.events.append(("info", message))

    def error(self, message: str) -> None:
        self.events.append(("error", message))

    def messages(self, level: str) -> list[str]:
        """All messages recorded at ``level``, in order."""
        return [message for lvl, message in self.events if lvl == level]


class FakeConfirmer:
    """A `Confirmer` that records prompts and returns queued (or default) answers."""

    def __init__(self, answers: Iterable[bool] = (), *, default: bool = True) -> None:
        self._answers = list(answers)
        self._default = default
        self.prompts: list[str] = []

    def confirm(self, prompt: str, *, default: bool = False) -> bool:
        self.prompts.append(prompt)
        return self._answers.pop(0) if self._answers else self._default


class FakePrompter:
    """A `Prompter` that records questions and returns queued answers (else default)."""

    def __init__(self, answers: Iterable[str] = ()) -> None:
        self._answers = list(answers)
        self.asked: list[tuple[str, bool]] = []

    def ask(self, label: str, *, default: str | None = None, secret: bool = False) -> str | None:
        self.asked.append((label, secret))
        return self._answers.pop(0) if self._answers else default
