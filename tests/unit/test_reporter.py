"""Increment 7 — the Reporter seam: console UX decoupled from rich.

The Reporter announces human-facing *events* (step/ok/skip/warn/info/error). It
is separate from the audit log (compliance): the audit log must be complete and
structured; the reporter is best-effort presentation. RecordingReporter lets
tests assert on the events; NullReporter is the quiet default.
"""
from io import StringIO

from provisio import NullReporter, Reporter
from provisio.reporting import ConsoleReporter
from provisio.testing import RecordingReporter


def test_recording_reporter_is_a_reporter() -> None:
    assert isinstance(RecordingReporter(), Reporter)


def test_null_reporter_is_a_reporter() -> None:
    assert isinstance(NullReporter(), Reporter)


def test_recording_reporter_captures_events_in_order() -> None:
    reporter = RecordingReporter()
    reporter.step(1, 3, "Create RG")
    reporter.ok("created")
    reporter.skip("exists")
    reporter.warn("careful")
    reporter.info("fyi")
    reporter.error("boom")
    assert reporter.events == [
        ("step", "Create RG"),
        ("ok", "created"),
        ("skip", "exists"),
        ("warn", "careful"),
        ("info", "fyi"),
        ("error", "boom"),
    ]


def test_recording_reporter_messages_by_level() -> None:
    reporter = RecordingReporter()
    reporter.ok("a")
    reporter.ok("b")
    reporter.skip("c")
    assert reporter.messages("ok") == ["a", "b"]
    assert reporter.messages("skip") == ["c"]


def test_null_reporter_is_silent_and_safe() -> None:
    reporter = NullReporter()
    reporter.step(1, 1, "x")
    reporter.ok("y")
    reporter.error("z")  # must not raise


def test_console_reporter_writes_the_message_text() -> None:
    from rich.console import Console

    buffer = StringIO()
    reporter = ConsoleReporter(console=Console(file=buffer, force_terminal=False, width=80))
    reporter.ok("created rg")
    reporter.step(2, 5, "Storage")
    output = buffer.getvalue()
    assert "created rg" in output
    assert "Storage" in output


def test_status_markers_are_ascii_safe() -> None:
    # Regression: Unicode glyphs (✓/→/⚠) crash on a legacy Windows cp1252 console.
    # The status markers must stay ASCII-safe (the rule/box chars are handled by rich).
    from rich.console import Console

    buffer = StringIO()
    reporter = ConsoleReporter(console=Console(file=buffer, force_terminal=True, width=80))
    reporter.ok("a")
    reporter.skip("b")
    reporter.warn("c")
    reporter.error("d")
    buffer.getvalue().encode("ascii")  # must not raise
