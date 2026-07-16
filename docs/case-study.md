# Case study: from script to framework

`provisio` was extracted from a real, procedural provisioning CLI — roughly 600 lines
across five files, with **zero tests** — that stood up a production Azure stack
(resource group, storage account + file share, Key Vault, Container Apps, a Static Web
App, a self-hosted CI runner VM, managed-identity RBAC, and CI secrets). Rebuilding
that CLI as a `provisio` app is what shaped the SDK.

## Before → after

| Before (a procedural script) | After (a `provisio` app) |
|---|---|
| Procedural functions, 0 tests | Steps declared on `provisio`, fully unit-tested (fake runner) |
| CLI framework coupled into the domain | Domain touches neither; the CLI is generated |
| Config declared twice (a dataclass **and** the CLI signature) | One `Setting` schema drives CLI + resolution + redaction |
| Values threaded through module-level locals | Typed `OutputKey`s validated before anything runs |
| Four copy-pasted patterns | `ensure` / `update_if_confirmed` / `poll_until` |
| No audit trail, no state | Redacted audit log + `diff` CI gate |

## A step is pure intent

```python
@step("resource-group", "Create resource group")
def resource_group(ctx):
    az, cfg = ctx.tool("az"), ctx.settings
    ensure(ctx, describe=f"resource group '{cfg.resource_group}'",
           exists=lambda: az.exists("group", "show", "--name", cfg.resource_group),
           create=lambda: az("group", "create", "--name", cfg.resource_group, "--location", cfg.location))
```

## The whole orchestration is one list

A hand-threaded `try/except` and a step table collapse to an explicit, reviewable plan:

```python
def build_plan() -> Plan:
    return Plan([
        steps.prerequisites, steps.subscription, steps.resource_group, steps.storage,
        steps.keyvault, steps.container_env, steps.static_web_app, steps.kv_secrets,
        steps.data_upload, steps.container_app, steps.principal, steps.kv_access,
        steps.env_secrets, steps.file_share_mount, steps.registry, steps.runner_vm,
        steps.ci_secrets,
    ])
```

## The CLI is a few lines

```python
from provisio import build_cli
from myapp.application import app_spec   # InfraApplication(name, plan, settings, tools)
cli = build_cli(app_spec)                # -> `myinfra apply` / `myinfra diff`
```

## Parity, with zero cloud

An end-to-end test runs the whole plan through the fake runner and asserts it issues
the same `az` commands the original script did — parity, with no cloud access and no
credentials.
