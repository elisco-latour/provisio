"""Increment 3 — the CommandRunner seam and its test double.

`CommandRunner` is the single door to the outside world. `FakeCommandRunner`
(shipped in `provisio.testing`) records argv and returns canned results, so any
consumer can test their infrastructure glue with zero cloud access.
"""
import pytest

from provisio import CommandFailedError, CommandRunner
from provisio.testing import FakeCommandRunner


def test_fake_is_a_command_runner() -> None:
    assert isinstance(FakeCommandRunner(), CommandRunner)


def test_records_argv_in_order() -> None:
    fake = FakeCommandRunner()
    fake.run(["az", "group", "show"])
    fake.run(["gh", "auth", "status"])
    assert fake.calls == [("az", "group", "show"), ("gh", "auth", "status")]


def test_returns_canned_result_by_prefix() -> None:
    fake = FakeCommandRunner()
    fake.stub("az", "account", "show", stdout="sub-123")
    result = fake.run(["az", "account", "show", "--query", "id"])
    assert result.stdout == "sub-123"
    # the result reflects the *actual* argv that was run, not just the prefix
    assert result.args == ("az", "account", "show", "--query", "id")


def test_unmatched_call_defaults_to_success() -> None:
    fake = FakeCommandRunner()
    result = fake.run(["az", "anything"])
    assert result.ok
    assert result.stdout == ""


def test_check_raises_command_failed_error() -> None:
    fake = FakeCommandRunner()
    fake.stub("az", "boom", returncode=2, stderr="nope")
    with pytest.raises(CommandFailedError):
        fake.run(["az", "boom"])


def test_check_false_returns_failure_without_raising() -> None:
    fake = FakeCommandRunner()
    fake.stub("az", "boom", returncode=2)
    result = fake.run(["az", "boom"], check=False)
    assert result.returncode == 2
    assert not result.ok


def test_issued_prefix_helper() -> None:
    fake = FakeCommandRunner()
    fake.run(["az", "group", "create", "--name", "x"])
    assert fake.issued("az", "group", "create")
    assert not fake.issued("az", "group", "delete")
