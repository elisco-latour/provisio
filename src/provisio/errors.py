"""The provisio exception hierarchy.

Everything provisio raises derives from `ProvisioError`, so an application (or the
generated CLI) can catch that one base type and map it to an exit code in a single
place, without leaking framework internals.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-only import: keeps errors.py free of a runtime dependency on command.py,
    # so command.py's runners can import CommandFailedError without a cycle.
    from provisio.command import CommandResult


class ProvisioError(Exception):
    """Base class for every error provisio raises."""


class ExecutableNotFoundError(ProvisioError):
    """Raised when a command's executable cannot be found on PATH."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"executable '{name}' not found on PATH — is it installed?")


class MissingOutputError(ProvisioError):
    """Raised when a step reads an output that no prior step has produced."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"required output {name!r} has not been produced")


class StepFailedError(ProvisioError):
    """Wraps an *unexpected* exception raised inside a step, naming the step.

    Domain errors (`ProvisioError` subclasses) propagate unwrapped — they already
    carry good messages; this exists to attach the failing step's key to
    surprises (bugs, KeyError, ...).
    """

    def __init__(self, key: str, cause: Exception) -> None:
        self.key = key
        self.cause = cause
        super().__init__(f"step {key!r} failed: {cause}")


class CommandFailedError(ProvisioError):
    """Raised when a *checked* command exits non-zero.

    Carries the full `CommandResult` so callers can inspect the exit code and
    streams. Note: the message includes the argv for debuggability; secret
    redaction is applied at the logging/reporting boundary (see logging.py).
    """

    def __init__(self, result: CommandResult) -> None:
        self.result = result
        message = f"command exited {result.returncode}: {' '.join(result.args)}"
        if result.stderr.strip():
            message = f"{message}\n{result.stderr.strip()}"
        super().__init__(message)
