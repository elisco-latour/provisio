"""Increment 11 — confirm-then-update and poll primitives + interaction ports.

`update_if_confirmed` collapses the legacy `_confirm_update` pattern; the TTY/--yes
logic now lives in `Confirmer` implementations, so the domain never touches typer
or sys.stdin. `poll_until` collapses the provisioning-state wait, with `sleep`
injected so tests are instant.
"""
import pytest

from provisio import (
    AutoConfirmer,
    Confirmer,
    ExecutionContext,
    Prompter,
    ProvisioError,
    poll_until,
    update_if_confirmed,
)
from provisio.testing import FakeConfirmer, FakePrompter, RecordingReporter


def test_auto_confirmer_returns_fixed_answer() -> None:
    assert isinstance(AutoConfirmer(True), Confirmer)
    assert AutoConfirmer(True).confirm("proceed?") is True
    assert AutoConfirmer(False).confirm("proceed?") is False


def test_fake_prompter_is_a_prompter() -> None:
    assert isinstance(FakePrompter(), Prompter)


def test_update_applies_directly_when_no_prompt() -> None:
    reporter = RecordingReporter()
    ctx = ExecutionContext(reporter=reporter)
    applied: list[int] = []
    update_if_confirmed(ctx, describe="env vars", apply=lambda: applied.append(1), prompt=None)
    assert applied == [1]
    assert reporter.messages("ok") == ["env vars"]


def test_update_applies_when_confirmed() -> None:
    ctx = ExecutionContext(reporter=RecordingReporter(), confirm=FakeConfirmer([True]))
    applied: list[int] = []
    update_if_confirmed(ctx, describe="env vars", apply=lambda: applied.append(1), prompt="update?")
    assert applied == [1]


def test_update_skips_when_declined() -> None:
    reporter = RecordingReporter()
    ctx = ExecutionContext(reporter=reporter, confirm=FakeConfirmer([False]))
    applied: list[int] = []
    update_if_confirmed(ctx, describe="env vars", apply=lambda: applied.append(1), prompt="update?")
    assert applied == []
    assert reporter.messages("skip") == ["env vars"]


def test_default_context_confirm_proceeds() -> None:
    # The default context confirmer auto-answers yes (matches legacy non-interactive).
    ctx = ExecutionContext(reporter=RecordingReporter())
    applied: list[int] = []
    update_if_confirmed(ctx, describe="env", apply=lambda: applied.append(1), prompt="update?")
    assert applied == [1]


def test_poll_returns_when_done() -> None:
    ctx = ExecutionContext(reporter=RecordingReporter())
    states = iter(["Creating", "Creating", "Succeeded"])
    result = poll_until(
        ctx,
        describe="environment",
        read_state=lambda: next(states),
        done={"Succeeded"},
        failed={"Failed"},
        sleep=lambda _seconds: None,
    )
    assert result == "Succeeded"


def test_poll_raises_on_failed_state() -> None:
    ctx = ExecutionContext(reporter=RecordingReporter())
    with pytest.raises(ProvisioError):
        poll_until(
            ctx,
            describe="environment",
            read_state=lambda: "Failed",
            done={"Succeeded"},
            failed={"Failed"},
            sleep=lambda _seconds: None,
        )


def test_poll_times_out() -> None:
    ctx = ExecutionContext(reporter=RecordingReporter())
    with pytest.raises(ProvisioError):
        poll_until(
            ctx,
            describe="environment",
            read_state=lambda: "Creating",
            done={"Succeeded"},
            timeout=30,
            interval=15,
            sleep=lambda _seconds: None,
        )
