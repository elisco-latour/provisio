# State, diff & audit

## The CI re-provisioning gate

Because `provisio` has no resource model, it does not diff cloud state. Instead it
persists the **declaration** — the plan/input fingerprints, per-step status, and
produced outputs — and diffs *that* across versions.

```bash
# Fails CI-style: 0 = no changes, 2 = changes present, 1 = error.
myinfra diff --state infra.state.json

# Persist state on a successful apply.
myinfra apply --yes --state infra.state.json
```

A typical CI gate:

```yaml
- run: myinfra diff --state infra.state.json || code=$?; [ "${code:-0}" = 2 ] && myinfra apply --yes --state infra.state.json
```

What the diff detects: **added / removed / changed steps** (a step's fingerprint
covers its declaration and its action source) and whether **inputs changed**. What it
does *not* detect: out-of-band cloud drift. That honesty is by design — re-running
`apply` is already cheap and safe because every step is idempotent.

Secrets are never stored raw: inputs are captured only as a one-way fingerprint, and
outputs declared `OutputKey("...", secret=True)` are hashed in the state file.

## Audit logging (compliance)

Every command that runs is logged — command + exit code — to a namespaced stdlib
logger, with secret values redacted. It is a first-class, reusable logger, separate
from the pretty console output.

```python
from provisio import configure_audit_log, Redactor, get_logger

configure_audit_log(destination="audit.jsonl", fmt="json", redactor=Redactor(["my-secret"]))
get_logger("provisio.myapp").info("starting run")   # reuse it in your own code
```

- `destination`: `"stdout"`, `"stderr"`, or a file path (the CLI exposes `--log-file`).
- `fmt`: `text` (human) or `json` (for SIEM ingestion) — the CLI exposes `--log-format`.
- Redaction is a tested invariant: no secret value ever appears in a log line.

**`--dry-run` is audited too.** A preview writes a `dry-run` marker and a
`would-run` / `would-skip` record per step, so previews leave a compliance trace
just like a real apply — no commands run and no credentials are needed. Use
`--log-file` to keep the audit trail separate from the on-screen preview.
