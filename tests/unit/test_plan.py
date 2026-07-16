"""Increment 12 — Step/@step/command_step, Plan, and RunResult.

Plan sequences steps explicitly (the list IS the feature — no DAG auto-ordering),
validates output wiring up front, emits reporter/audit events, and returns a
RunResult usable programmatically (the Terraform-glue / library entry point).
"""
import pytest

from provisio import (
    CliTool,
    ExecutionContext,
    MissingOutputError,
    OutputKey,
    Plan,
    ProvisioError,
    command_step,
    step,
)
from provisio.errors import StepFailedError
from provisio.plan import PreviewLine, RunResult, Step, StepResult
from provisio.testing import FakeCommandRunner, RecordingReporter


def test_step_decorator_builds_a_step() -> None:
    @step("k", "Title")
    def s(ctx: ExecutionContext) -> None: ...

    assert isinstance(s, Step)
    assert s.key == "k"
    assert s.title == "Title"


def test_plan_runs_steps_in_declared_order() -> None:
    order: list[str] = []
    plan = Plan(
        [
            step("one", "One")(lambda ctx: order.append("one")),
            step("two", "Two")(lambda ctx: order.append("two")),
        ]
    )
    plan.execute(ExecutionContext())
    assert order == ["one", "two"]


def test_execute_returns_runresult_with_status_and_outputs() -> None:
    greeting: OutputKey[str] = OutputKey("greeting")
    plan = Plan([step("g", "Greet", produces=(greeting,))(lambda ctx: ctx.set(greeting, "hi"))])

    result = plan.execute(ExecutionContext())

    assert isinstance(result, RunResult)
    assert result.ok
    assert result.outputs["greeting"] == "hi"
    assert result.steps == (StepResult(key="g", title="Greet", status="ran"),)


def test_skip_marks_step_and_does_not_run_it() -> None:
    ran: list[str] = []
    plan = Plan(
        [
            step("a", "A")(lambda ctx: ran.append("a")),
            step("b", "B")(lambda ctx: ran.append("b")),
        ]
    )
    result = plan.execute(ExecutionContext(reporter=RecordingReporter()), skip=["a"])
    assert ran == ["b"]
    assert result.steps[0].status == "skipped"


def test_validate_rejects_requires_not_produced_upstream() -> None:
    need: OutputKey[str] = OutputKey("need")
    plan = Plan([step("c", "C", requires=(need,))(lambda ctx: None)])
    with pytest.raises(MissingOutputError):
        plan.validate()


def test_validate_accepts_requires_produced_upstream() -> None:
    key: OutputKey[str] = OutputKey("k")
    plan = Plan(
        [
            step("p", "P", produces=(key,))(lambda ctx: ctx.set(key, "v")),
            step("c", "C", requires=(key,))(lambda ctx: ctx.get(key)),
        ]
    )
    plan.validate()  # must not raise
    plan.execute(ExecutionContext())


def test_runtime_requires_check_when_producer_skipped() -> None:
    key: OutputKey[str] = OutputKey("k")
    plan = Plan(
        [
            step("p", "P", produces=(key,))(lambda ctx: ctx.set(key, "v")),
            step("c", "C", requires=(key,))(lambda ctx: ctx.get(key)),
        ]
    )
    with pytest.raises(MissingOutputError):
        plan.execute(ExecutionContext(), skip=["p"])


def test_unexpected_error_is_wrapped_as_step_failed() -> None:
    def boom(ctx: ExecutionContext) -> None:
        raise ValueError("kaboom")

    plan = Plan([step("x", "X")(boom)])
    with pytest.raises(StepFailedError) as exc_info:
        plan.execute(ExecutionContext())
    assert exc_info.value.key == "x"


def test_provisio_error_propagates_unwrapped() -> None:
    def boom(ctx: ExecutionContext) -> None:
        raise ProvisioError("domain problem")

    plan = Plan([step("x", "X")(boom)])
    with pytest.raises(ProvisioError) as exc_info:
        plan.execute(ExecutionContext())
    assert not isinstance(exc_info.value, StepFailedError)


def test_preview_lists_steps_and_marks_skipped() -> None:
    plan = Plan(
        [
            step("a", "Alpha")(lambda ctx: None),
            step("b", "Beta")(lambda ctx: None),
        ]
    )
    lines = plan.preview(skip=["b"])
    assert lines == [
        PreviewLine(index=1, total=2, title="Alpha", skipped=False, key="a"),
        PreviewLine(index=2, total=2, title="Beta", skipped=True, key="b"),
    ]
    assert lines[1].render().endswith("(skipped)")


def test_dependency_edges_derived_from_produces_and_requires() -> None:
    key: OutputKey[str] = OutputKey("k")
    plan = Plan(
        [
            step("p", "P", produces=(key,))(lambda ctx: None),
            step("c", "C", requires=(key,))(lambda ctx: None),
        ]
    )
    assert plan.dependency_edges() == [("p", "c")]


def test_dry_run_reports_preview_and_writes_audit_records(tmp_path) -> None:
    import json

    from provisio import configure_audit_log, get_logger

    log_file = tmp_path / "audit.jsonl"
    configure_audit_log(destination=log_file, fmt="json")

    ran: list[str] = []
    plan = Plan(
        [
            step("a", "Alpha")(lambda ctx: ran.append("a")),
            step("b", "Beta")(lambda ctx: ran.append("b")),
        ]
    )
    reporter = RecordingReporter()
    lines = plan.dry_run(ExecutionContext(reporter=reporter), skip=["b"])

    for handler in get_logger().handlers:
        handler.flush()

    assert ran == []  # nothing executed
    assert len(lines) == 2
    assert any("Alpha" in m for m in reporter.messages("info"))  # preview shown

    records = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    actions = [r.get("action") for r in records]
    assert "dry-run" in actions
    assert any(r.get("action") == "would-run" and r.get("step") == "a" for r in records)
    assert any(r.get("action") == "would-skip" and r.get("step") == "b" for r in records)


def test_command_step_runs_the_raw_command() -> None:
    # L1 on-ramp: wrap an existing command as a step in ~1 line, no idempotency.
    fake = FakeCommandRunner()
    ctx = ExecutionContext(tools={"az": CliTool("az", fake)})
    plan = Plan([command_step("rg", "Resource group", "az", "group", "create", "--name", "demo")])
    plan.execute(ctx)
    assert fake.issued("az", "group", "create", "--name", "demo")
