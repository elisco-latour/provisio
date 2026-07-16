"""Increment 12 — the simplicity-budget acceptance gate (a HARD constraint).

Provisioning one real resource must fit in a handful of readable lines using only
the bare core (no CLI/state/audit ceremony), with the context defaulted. If this
balloons, the design has drifted and the change is wrong.
"""
from provisio import CliTool, ExecutionContext, Plan, ensure, step
from provisio.testing import FakeCommandRunner


def test_hello_world_provisions_one_resource() -> None:
    # --- the whole "hello world" a user writes -------------------------------
    @step("rg", "Resource group")
    def rg(ctx: ExecutionContext) -> None:
        az = ctx.tool("az")
        ensure(
            ctx,
            describe="resource group 'demo'",
            exists=lambda: az.exists("group", "show", "--name", "demo"),
            create=lambda: az("group", "create", "--name", "demo", "--location", "eastus2"),
        )

    runner = FakeCommandRunner()
    ctx = ExecutionContext(tools={"az": CliTool("az", runner)})
    Plan([rg]).execute(ctx)
    # -------------------------------------------------------------------------

    # First run: nothing exists (fake defaults to success, so stub the probe as absent).
    # Re-running against an existing resource must be a no-op (idempotent).
    existing = FakeCommandRunner().stub("az", "group", "show", returncode=0)
    ctx2 = ExecutionContext(tools={"az": CliTool("az", existing)})
    Plan([rg]).execute(ctx2)
    assert not existing.issued("az", "group", "create")


def test_hello_world_creates_when_absent() -> None:
    @step("rg", "Resource group")
    def rg(ctx: ExecutionContext) -> None:
        az = ctx.tool("az")
        ensure(
            ctx,
            describe="resource group 'demo'",
            exists=lambda: az.exists("group", "show", "--name", "demo"),
            create=lambda: az("group", "create", "--name", "demo", "--location", "eastus2"),
        )

    absent = FakeCommandRunner().stub("az", "group", "show", returncode=3)
    ctx = ExecutionContext(tools={"az": CliTool("az", absent)})
    Plan([rg]).execute(ctx)
    assert absent.issued("az", "group", "create", "--name", "demo")
