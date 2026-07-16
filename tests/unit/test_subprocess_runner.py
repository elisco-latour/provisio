"""Increment 4 — the real runner, exercised against a harmless local subprocess.

We deliberately drive `sys.executable` (the current Python), never a cloud CLI:
the real runner's job is argv resolution + capture + check semantics, and that is
fully verifiable without any cloud.
"""
import sys

import pytest

from provisio import CommandFailedError, SubprocessCommandRunner
from provisio.errors import ExecutableNotFoundError


def test_runs_real_argv_and_captures_stdout() -> None:
    runner = SubprocessCommandRunner()
    result = runner.run([sys.executable, "-c", "print('hello')"])
    assert result.ok
    assert result.stdout.strip() == "hello"


def test_captures_returncode_and_stderr_when_not_checked() -> None:
    runner = SubprocessCommandRunner()
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"],
        check=False,
    )
    assert result.returncode == 3
    assert "boom" in result.stderr
    assert not result.ok


def test_check_raises_command_failed_error() -> None:
    runner = SubprocessCommandRunner()
    with pytest.raises(CommandFailedError):
        runner.run([sys.executable, "-c", "import sys; sys.exit(1)"])


def test_missing_executable_raises() -> None:
    runner = SubprocessCommandRunner()
    with pytest.raises(ExecutableNotFoundError):
        runner.run(["provisio-nonexistent-binary-zzz", "arg"])
