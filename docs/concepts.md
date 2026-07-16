# Concepts

`provisio` is deliberately small — the whole framework is a handful of composable
pieces, and `primitives.py` + `plan.py` are readable in one sitting. Composition is
preferred over inheritance throughout: a step is configured entirely by what is
injected into its `ExecutionContext`.

## The pieces

| Concept | Responsibility |
|---|---|
| `CommandResult` | Transport-neutral result of one command (`args`, `returncode`, `stdout`, `stderr`, `.ok`, `.json()`). |
| `CommandRunner` | The one door to the outside world. `SubprocessCommandRunner` is real; `FakeCommandRunner` (in `provisio.testing`) records argv and returns canned output. |
| `CliTool` | A generic vendor-CLI facade. `az`/`gh`/`gcloud`/`aws` are all instances; the binary and its JSON/TSV flags are **configured, not assumed**. |
| `Reporter` | Human-facing console UX (`Null`/`Console`/`Recording`), separate from the audit log. |
| audit `logging` | A namespaced stdlib logger (`provisio.*`), reusable anywhere, with secret redaction. |
| `Setting` / `resolve_settings` | One declaration per option, driving resolution **and** the CLI **and** redaction. |
| `OutputKey` / `ExecutionContext` | Typed outputs threaded between steps, replacing fragile string-keyed value passing. |
| `ensure` / `update_if_confirmed` / `poll_until` | The recurring provisioning patterns, single-sourced. |
| `Step` / `Plan` / `RunResult` | A named unit of work; an explicit ordered list; a programmatic result. |
| `State` / `diff` | Declaration-level state + a change diff for the CI gate. |
| `InfraApplication` / `build_cli` | Declare an app once; generate its Click CLI. |

## Honest tradeoffs

These are stated up front so you can decide if `provisio` fits:

- **The CLI seam gives test isolation, not provider independence.** Step bodies still
  write real argv (`az group create ...`). `CliTool` quarantines per-CLI specifics, so
  *adding* a cloud means adding steps + a tool spec — not rearchitecting — but it is
  not a free "swap the backend" abstraction, and the docs will not pretend it is.
- **`provisio` structures idempotency; it does not provide it.** You write the
  existence probe and the create action; a wrong probe is your bug. The framework
  gives you a tested place to put that logic, not a resource model that knows it for you.
- **State/diff is declaration-level, not cloud drift.** It answers "did *our*
  definition change since last apply?" (a CI gate), not "did someone change the cloud
  out of band?". Real drift detection is a named future capability, not a v1 promise.
- **Provision-only (v1).** `provisio` does create/ensure. In-place *updates* and
  *teardown*/`destroy` are explicit non-goals for now; `diff` surfaces removed/changed
  steps for a human, but performs no automated deletion.

## What we deliberately refuse

No DAG auto-ordering (the explicit plan list *is* the feature), no plugin discovery,
no generic retry framework beyond `poll_until`, no parsing of argv into a typed
resource model. Keeping these out is what keeps the framework small enough to trust.
