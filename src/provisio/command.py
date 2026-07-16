"""The command layer: the single door between provisio and the outside world.

`CommandResult` is a transport-neutral value object — it does not know whether it
came from a subprocess, an SSH session, or (one day) a cloud SDK. Keeping it free
of `subprocess` specifics is what lets the test fake construct results directly and
lets a future runner implementation slot in without touching callers.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from provisio.errors import CommandFailedError, ExecutableNotFoundError

# Every command that actually runs is recorded here for the audit trail. Secret
# redaction happens at the configured handler (see logging.py), so the runner
# logs the argv verbatim and stays ignorant of what is secret.
_AUDIT_LOG = logging.getLogger("provisio.command")


@dataclass(frozen=True, slots=True)
class CommandResult:
    """The immutable outcome of running one external command.

    Attributes:
        args: the argv that was run, e.g. ``("az", "group", "show", ...)``.
        returncode: the process exit code (0 conventionally means success).
        stdout: captured standard output.
        stderr: captured standard error.
    """

    args: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        """True when the command exited successfully (return code 0)."""
        return self.returncode == 0

    def json(self) -> Any:
        """Parse ``stdout`` as JSON.

        The caller is responsible for having asked the underlying CLI for JSON
        output; this is a convenience, not a guarantee.
        """
        return json.loads(self.stdout)


@runtime_checkable
class CommandRunner(Protocol):
    """Runs an argv and returns a `CommandResult`. The only door to the outside.

    Implementations share nothing but this contract — the real runner shells out
    to a subprocess; the test fake returns canned results. Everything that would
    touch a cloud goes through here, which is what makes the framework testable.
    """

    def run(self, args: Sequence[str], *, check: bool = True) -> CommandResult:
        """Run ``args`` and return the result.

        Args:
            args: the argv to run, e.g. ``["az", "group", "show", "--name", "rg"]``.
            check: when True a non-zero exit raises `CommandFailedError`; when
                False the failing `CommandResult` is returned (used by existence probes).
        """
        ...


class SubprocessCommandRunner:
    """The real `CommandRunner`: resolve argv[0] on PATH, run it, capture output.

    This is the only place `subprocess` lives. It performs no cloud-specific
    logic — it just runs whatever argv it is given (``az ...``, ``gh ...``,
    ``aws ...``) and returns a `CommandResult`.
    """

    def run(self, args: Sequence[str], *, check: bool = True) -> CommandResult:
        argv = [str(a) for a in args]
        if not argv:
            raise ValueError("args must not be empty")

        executable = shutil.which(argv[0])
        if executable is None:
            raise ExecutableNotFoundError(argv[0])

        completed = subprocess.run(  # noqa: S603 - argv is caller-supplied by design
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
        )
        result = CommandResult(
            args=tuple(argv),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        # Audit every command that runs (success or failure), before honouring
        # `check`, so failed commands are recorded too. The command string is in
        # the message (for text logs) and as a structured field (for json logs).
        command = " ".join(argv)
        _AUDIT_LOG.info(
            "command exited %d: %s",
            result.returncode,
            command,
            extra={"command": command, "exit_code": result.returncode},
        )
        if check and not result.ok:
            raise CommandFailedError(result)
        return result
