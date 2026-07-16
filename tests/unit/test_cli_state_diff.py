"""Increment 17 — the `diff` command + `apply` writing state.

`apply` persists the last-applied declaration (fingerprints + step statuses +
redacted outputs) to the state store. `diff` compares the current definition to it
and returns Terraform-style exit codes: 0 = no changes, 2 = changes, 1 = error —
so CI can branch on it to decide whether to re-provision.
"""
import sys

from click.testing import CliRunner

from provisio import OutputKey, Plan, command_step, step
from provisio.application import CliToolSpec, InfraApplication
from provisio.app_cli import build_cli


def _app(*, plan: Plan, settings=(), tools=()) -> InfraApplication:
    return InfraApplication(name="demo", help="Demo app", plan=plan, settings=tuple(settings), tools=tuple(tools))


def _py_tools() -> tuple[CliToolSpec, ...]:
    return (CliToolSpec("py", binary=sys.executable),)


def test_apply_writes_state_file(tmp_path) -> None:
    state = tmp_path / "state.json"
    app = _app(plan=Plan([command_step("noop", "No-op", "py", "-c", "pass")]), tools=_py_tools())
    result = CliRunner().invoke(
        build_cli(app),
        ["apply", "--yes", "--state", str(state), "--log-file", str(tmp_path / "a.log")],
    )
    assert result.exit_code == 0, result.output
    assert state.exists()


def test_diff_exit_0_when_unchanged(tmp_path) -> None:
    state = tmp_path / "state.json"
    app = _app(plan=Plan([command_step("noop", "No-op", "py", "-c", "pass")]), tools=_py_tools())
    cli = build_cli(app)
    CliRunner().invoke(cli, ["apply", "--yes", "--state", str(state), "--log-file", str(tmp_path / "a.log")])

    result = CliRunner().invoke(cli, ["diff", "--state", str(state)])
    assert result.exit_code == 0, result.output


def test_diff_exit_2_when_plan_changed(tmp_path) -> None:
    state = tmp_path / "state.json"
    before = _app(plan=Plan([command_step("a", "A", "py", "-c", "pass")]), tools=_py_tools())
    CliRunner().invoke(build_cli(before), ["apply", "--yes", "--state", str(state), "--log-file", str(tmp_path / "a.log")])

    after = _app(
        plan=Plan([command_step("a", "A", "py", "-c", "pass"), command_step("b", "B", "py", "-c", "pass")]),
        tools=_py_tools(),
    )
    result = CliRunner().invoke(build_cli(after), ["diff", "--state", str(state)])
    assert result.exit_code == 2, result.output


def test_diff_exit_2_on_first_apply(tmp_path) -> None:
    app = _app(plan=Plan([command_step("a", "A", "py", "-c", "pass")]), tools=_py_tools())
    result = CliRunner().invoke(build_cli(app), ["diff", "--state", str(tmp_path / "absent.json")])
    assert result.exit_code == 2


def test_apply_hashes_secret_output_in_state(tmp_path) -> None:
    state = tmp_path / "state.json"
    token: OutputKey[str] = OutputKey("token", secret=True)

    @step("emit", "Emit token", produces=(token,))
    def emit(ctx) -> None:
        ctx.set(token, "SUPERSECRET")

    app = _app(plan=Plan([emit]))
    result = CliRunner().invoke(
        build_cli(app),
        ["apply", "--yes", "--state", str(state), "--log-file", str(tmp_path / "a.log")],
    )
    assert result.exit_code == 0, result.output
    text = state.read_text()
    assert "SUPERSECRET" not in text  # hashed, never raw
    assert '"token"' in text  # but present as a key
