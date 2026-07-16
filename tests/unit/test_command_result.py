"""Increment 2 — CommandResult: the transport-neutral outcome of one command.

It knows nothing about az/gh/subprocess; it is trivially constructable by the
test fake and hides whether a result came from a process or (future) an SDK.
"""
import pytest

from provisio import CommandResult


def test_ok_is_true_when_returncode_zero() -> None:
    result = CommandResult(args=("az", "version"), returncode=0, stdout="{}")
    assert result.ok is True


def test_ok_is_false_when_returncode_nonzero() -> None:
    result = CommandResult(args=("az", "boom"), returncode=3, stderr="not found")
    assert result.ok is False


def test_json_parses_stdout() -> None:
    result = CommandResult(args=("az", "group", "show"), returncode=0, stdout='{"id": "abc"}')
    assert result.json() == {"id": "abc"}


def test_is_immutable() -> None:
    result = CommandResult(args=("az",), returncode=0)
    with pytest.raises(Exception):
        result.returncode = 1  # type: ignore[misc]
