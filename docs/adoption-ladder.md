# The adoption ladder

`provisio`'s wedge is **no behaviour change**: it runs the commands you already run,
now idempotent, previewable, and audited — and you can adopt it **without rewriting**
your script. There is no cliff, only a ladder.

## L0 — rewrite nothing

Route your existing commands through a `CommandRunner` / `CliTool`. Instantly you get
a **redacted audit log** of every command and its exit code, and consistent error
handling — for essentially no code change.

```python
from provisio import CliTool, SubprocessCommandRunner, configure_audit_log
configure_audit_log(destination="audit.jsonl", fmt="json")
az = CliTool("az", SubprocessCommandRunner())
az("group", "create", "--name", "demo", "--location", "eastus2")  # audited
```

## L1 — wrap each command as a step (~1 line)

`command_step` turns a raw command into a step. Now you get **dry-run preview,
explicit ordering, `--skip`, and a `RunResult`** — still no idempotency.

```python
from provisio import Plan, command_step
Plan([
    command_step("rg", "Resource group", "az", "group", "create", "--name", "demo", "--location", "eastus2"),
]).execute(ctx)
```

## L2 — add an existence probe

Wrap the create in `ensure` with an `exists=` probe and the step becomes
**idempotent** — safe to re-run.

```python
from provisio import step, ensure

@step("rg", "Resource group")
def rg(ctx):
    az = ctx.tool("az")
    ensure(ctx, describe="resource group 'demo'",
           exists=lambda: az.exists("group", "show", "--name", "demo"),
           create=lambda: az("group", "create", "--name", "demo", "--location", "eastus2"))
```

## L3 — the full framework

Add `requires`/`produces` to thread typed outputs, a `Setting` schema to get a
generated CLI, and state so `diff` gates re-provisioning in CI. See the
[case study](case-study.md) for a complete app at this level.

## Using provisio inside a Terraform/Pulumi project

`provisio` is **library-first** — `Plan.execute(ctx)` returns a `RunResult`, no CLI
required — so it drops straight into the imperative glue a TF/Pulumi project is forced
to write anyway (`local-exec` / `null_resource` / `Command`), plus bootstrap
(pre-Terraform) resources and cross-tool orchestration (`gh`, `kubectl`). Pass
Terraform outputs in via environment variables; read `provisio`'s outputs back out of
its state JSON. It does not touch Terraform's core (state/drift/updates) — it upgrades
its worst part.
