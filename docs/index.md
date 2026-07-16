# provisio

**Compose, test, and audit CLI-driven infrastructure provisioning — over the vendor CLIs you already use.**

`provisio` is a small Python framework for the provisioning *scripts* teams already
write. It wraps the `az` / `gcloud` / `aws` / `gh` CLIs you already know and gives
them structure: idempotency, a fake-runner test harness, a compliance audit log, a
generated CLI, and a lightweight "did my infra definition change?" gate for CI.

## When *not* to use it

Be honest with yourself first. If you need **resource-graph diffing, drift
detection, a parallel dependency engine, a huge provider ecosystem, or remote state
with locking and collaboration**, use **Terraform or Pulumi** — that is what they are
built for, and `provisio` does not try to replace them.

`provisio`'s niche is narrower: it is the tested, idempotent, audited, CLI-generating
version of the bespoke `bash`/`az` glue that lives in every team's `scripts/` folder.
It *complements* the big IaC tools — and it is the disciplined home for the
`local-exec` / `null_resource` / `Command` escape hatch they force you into.

## What you get

- **No new DSL, engine, or provider model** — it's Python over the CLIs you know. A new
  CLI flag works the day the vendor ships it; no waiting for a provider.
- **Idempotency, structured** — the show-then-create pattern in one primitive.
- **Zero-cloud tests** — a fake runner records commands and returns canned output, so
  you unit-test your provisioning logic in milliseconds.
- **Compliance audit log** — every command + exit code, secrets redacted.
- **A generated CLI** — declare your settings once; get `apply`/`diff` with
  `--dry-run`, `--skip`, `--log-file`, and a state-diff exit code for CI.

## Install

```bash
pip install provisio            # core, dependency-free
pip install "provisio[cli]"     # + the generated Click CLI
pip install "provisio[rich]"    # + the colourful console reporter
```

## Hello world

Provisioning one resource, idempotently, needs only the bare core:

```python
from provisio import step, ensure, Plan, ExecutionContext, CliTool, SubprocessCommandRunner

@step("rg", "Resource group")
def rg(ctx):
    az = ctx.tool("az")
    ensure(ctx, describe="resource group 'demo'",
           exists=lambda: az.exists("group", "show", "--name", "demo"),
           create=lambda: az("group", "create", "--name", "demo", "--location", "eastus2"))

ctx = ExecutionContext(tools={"az": CliTool("az", SubprocessCommandRunner())})
Plan([rg]).execute(ctx)
```

Run it once and the group is created; run it again and it is skipped. Point it at an
existing script and you get a dry-run preview, safe re-runs, and an audit log —
**without rewriting anything** (see the [adoption ladder](adoption-ladder.md)).
