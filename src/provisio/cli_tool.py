"""The generic vendor-CLI facade.

`CliTool` is the *only* place that knows a binary's name and its output-format
flags. `az`, `gh`, `gcloud`, and `aws` are all just instances over the same
`CommandRunner`; they differ only in the binary and how they are asked for JSON
or TSV output (``-o json`` vs ``--format=json`` vs ``--output json``) — which is
*configured*, not assumed. Concentrating that per-CLI knowledge here is what keeps
`Plan`, `Reporter`, and the primitives cloud-agnostic.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from provisio.command import CommandResult, CommandRunner
from provisio.errors import ProvisioError


class CliTool:
    """A thin, callable wrapper around one CLI binary.

    Args:
        binary: the executable name, e.g. ``"az"``.
        runner: the `CommandRunner` all invocations go through.
        json_flags: flags appended by `json()` to request JSON output.
        tsv_flags: flags appended by `tsv()` to request tab/line output.
    """

    def __init__(
        self,
        binary: str,
        runner: CommandRunner,
        *,
        json_flags: Sequence[str] = (),
        tsv_flags: Sequence[str] = (),
    ) -> None:
        self._binary = binary
        self._runner = runner
        self._json_flags = tuple(json_flags)
        self._tsv_flags = tuple(tsv_flags)

    def __call__(self, *args: str, check: bool = True) -> str:
        """Run ``<binary> <args>`` and return stdout, stripped."""
        return self._runner.run([self._binary, *args], check=check).stdout.strip()

    def capture(self, *args: str, check: bool = True) -> CommandResult:
        """Run ``<binary> <args>`` and return the full `CommandResult`."""
        return self._runner.run([self._binary, *args], check=check)

    def exists(self, *args: str) -> bool:
        """Run a probe (``check=False``) and return True iff it exited 0.

        This is the building block of idempotency: it never raises on a non-zero
        exit, so a "does this resource exist?" query is just a failed probe.
        """
        return self._runner.run([self._binary, *args], check=False).ok

    def json(self, *args: str, check: bool = True) -> Any:
        """Run with the configured JSON flags appended and parse stdout as JSON."""
        if not self._json_flags:
            raise ProvisioError(
                f"CliTool({self._binary!r}) has no json_flags configured; "
                f"pass json_flags=... to use .json()"
            )
        return self._runner.run([self._binary, *args, *self._json_flags], check=check).json()

    def tsv(self, *args: str, check: bool = True) -> str:
        """Run with the configured TSV flags appended and return stdout, stripped."""
        if not self._tsv_flags:
            raise ProvisioError(
                f"CliTool({self._binary!r}) has no tsv_flags configured; "
                f"pass tsv_flags=... to use .tsv()"
            )
        return self._runner.run([self._binary, *args, *self._tsv_flags], check=check).stdout.strip()
