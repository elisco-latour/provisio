"""Increment 9 — ExecutionContext and typed OutputKeys.

The context is the bag of collaborators (tools, reporter, settings) + the outputs
produced so far that every step receives. Typed OutputKeys replace the fragile
string-keyed value-threading of the legacy CLI with a single definition site and
a clear MissingOutputError when a consumer runs before its producer.
"""
import pytest

from provisio import CliTool, ExecutionContext, NullReporter, OutputKey, ProvisioError
from provisio.errors import MissingOutputError
from provisio.testing import FakeCommandRunner

SUBSCRIPTION_ID: OutputKey[str] = OutputKey("subscription_id")


def test_defaults_keep_the_hello_world_short() -> None:
    ctx = ExecutionContext()
    assert isinstance(ctx.reporter, NullReporter)
    assert ctx.tools == {}


def test_set_get_roundtrip() -> None:
    ctx = ExecutionContext()
    ctx.set(SUBSCRIPTION_ID, "sub-123")
    assert ctx.get(SUBSCRIPTION_ID) == "sub-123"


def test_get_missing_output_raises() -> None:
    ctx = ExecutionContext()
    with pytest.raises(MissingOutputError):
        ctx.get(SUBSCRIPTION_ID)


def test_has_reflects_presence() -> None:
    ctx = ExecutionContext()
    assert ctx.has(SUBSCRIPTION_ID) is False
    ctx.set(SUBSCRIPTION_ID, "x")
    assert ctx.has(SUBSCRIPTION_ID) is True


def test_tool_returns_registered_instance() -> None:
    az = CliTool("az", FakeCommandRunner())
    ctx = ExecutionContext(tools={"az": az})
    assert ctx.tool("az") is az


def test_tool_unregistered_raises() -> None:
    ctx = ExecutionContext()
    with pytest.raises(ProvisioError):
        ctx.tool("az")


def test_output_key_is_frozen() -> None:
    key = OutputKey("x")
    with pytest.raises(Exception):
        key.name = "y"  # type: ignore[misc]
