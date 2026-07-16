"""Increment 10 — the ensure() idempotency primitive.

`ensure` collapses the show-then-create pattern (~10 copies in the legacy CLI)
into one place: if the probe says the resource exists, report a skip; otherwise
create it and report ok. Reporting fans out to both the console reporter (UX) and
the audit log (compliance) from this single site.
"""
import json

from provisio import CliTool, ExecutionContext, configure_audit_log, get_logger
from provisio.primitives import ensure
from provisio.testing import FakeCommandRunner, RecordingReporter


def test_ensure_skips_when_resource_exists() -> None:
    reporter = RecordingReporter()
    ctx = ExecutionContext(reporter=reporter)
    created: list[str] = []

    ensure(ctx, describe="rg 'demo'", exists=lambda: True, create=lambda: created.append("x"))

    assert created == []  # create must not run
    assert reporter.messages("skip") == ["rg 'demo'"]
    assert reporter.messages("ok") == []


def test_ensure_creates_when_resource_absent() -> None:
    reporter = RecordingReporter()
    ctx = ExecutionContext(reporter=reporter)
    created: list[str] = []

    ensure(ctx, describe="rg 'demo'", exists=lambda: False, create=lambda: created.append("x"))

    assert created == ["x"]
    assert reporter.messages("ok") == ["rg 'demo'"]
    assert reporter.messages("skip") == []


def test_ensure_idempotent_with_cli_probe() -> None:
    # Existence probe returns success -> resource exists -> no create issued.
    fake = FakeCommandRunner().stub("az", "group", "show", returncode=0)
    az = CliTool("az", fake)
    ctx = ExecutionContext(reporter=RecordingReporter(), tools={"az": az})

    ensure(
        ctx,
        describe="resource group",
        exists=lambda: az.exists("group", "show", "--name", "rg"),
        create=lambda: az("group", "create", "--name", "rg"),
    )

    assert not fake.issued("az", "group", "create")


def test_ensure_audit_logs_the_action(tmp_path) -> None:
    log_file = tmp_path / "audit.json"
    configure_audit_log(destination=log_file, fmt="json")
    ctx = ExecutionContext()

    ensure(ctx, describe="rg 'demo'", exists=lambda: False, create=lambda: None)
    for handler in get_logger().handlers:
        handler.flush()

    records = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    assert any(r.get("action") == "create" and r.get("resource") == "rg 'demo'" for r in records)
