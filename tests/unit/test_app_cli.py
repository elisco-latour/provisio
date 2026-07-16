"""Increment 14 — InfraApplication + build_cli (Click), the generated CLI.

The app declares itself once (plan + settings schema + tool specs); build_cli
turns that into a Click CLI whose options come from the same schema, plus the
standard framework flags. Verified with Click's CliRunner — no cloud.
"""
import sys

from click.testing import CliRunner

from provisio import Plan, Setting, command_step, step
from provisio.application import CliToolSpec, InfraApplication
from provisio.app_cli import build_cli


def _app(*, plan: Plan, settings=(), tools=()) -> InfraApplication:
    return InfraApplication(name="demo", help="Demo app", plan=plan, settings=tuple(settings), tools=tuple(tools))


def test_generated_cli_exposes_setting_option_from_schema() -> None:
    app = _app(plan=Plan([]), settings=(Setting("resource_group", default="rg", help="Resource group"),))
    result = CliRunner().invoke(build_cli(app), ["apply", "--help"])
    assert result.exit_code == 0
    assert "--resource-group" in result.output


def test_dry_run_lists_steps_and_exits_zero() -> None:
    plan = Plan(
        [
            step("a", "Alpha")(lambda ctx: None),
            step("b", "Beta")(lambda ctx: None),
        ]
    )
    result = CliRunner().invoke(build_cli(_app(plan=plan)), ["apply", "--dry-run"])
    assert result.exit_code == 0
    assert "Alpha" in result.output
    assert "Beta" in result.output


def test_dry_run_writes_audit_records(tmp_path) -> None:
    log_file = tmp_path / "audit.jsonl"
    plan = Plan([step("a", "Alpha")(lambda ctx: None), step("b", "Beta")(lambda ctx: None)])
    result = CliRunner().invoke(
        build_cli(_app(plan=plan)),
        ["apply", "--dry-run", "--skip", "b", "--log-file", str(log_file), "--log-format", "json"],
    )
    assert result.exit_code == 0
    text = log_file.read_text()
    assert "dry-run" in text
    assert "would-run" in text
    assert "would-skip" in text


def test_missing_cli_binary_errors_before_running() -> None:
    ran: list[int] = []
    plan = Plan([step("a", "A")(lambda ctx: ran.append(1))])
    app = _app(plan=plan, tools=(CliToolSpec("nope", binary="provisio-nonexistent-binary-zzz"),))
    result = CliRunner().invoke(build_cli(app), ["apply", "--yes"])
    assert result.exit_code != 0
    assert ran == []


def test_apply_executes_the_plan_and_writes_audit(tmp_path) -> None:
    log_file = tmp_path / "audit.json"
    plan = Plan([command_step("noop", "No-op", "py", "-c", "pass")])
    app = _app(plan=plan, tools=(CliToolSpec("py", binary=sys.executable),))
    result = CliRunner().invoke(
        build_cli(app),
        ["apply", "--yes", "--log-file", str(log_file), "--log-format", "json"],
    )
    assert result.exit_code == 0, result.output
    assert log_file.exists()
    assert "noop" in log_file.read_text()
