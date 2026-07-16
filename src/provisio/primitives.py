"""The generic, cloud-agnostic provisioning primitives.

These four small functions are the entire payoff of the framework: the recurring
patterns from the legacy CLI (show-then-create, confirm-then-update, poll, role
checks) collapse into single-sourced helpers so a step declares only intent.

Everything here is cloud-agnostic — it never names ``az``/``gcloud``/``aws``. A
step supplies the probe and the action (as closures over its own `CliTool`), and
the primitive owns the idempotency decision plus the reporter/audit fan-out.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Collection

from provisio.context import ExecutionContext
from provisio.errors import ProvisioError

# Step/resource lifecycle audit records (distinct from provisio.command, which
# records raw command execution). See logging.py for configuration.
_AUDIT_LOG = logging.getLogger("provisio.plan")


def ensure(
    ctx: ExecutionContext,
    *,
    describe: str,
    exists: Callable[[], bool],
    create: Callable[[], object],
) -> None:
    """Create a resource only if it is not already there (idempotent).

    Args:
        ctx: the execution context (for reporting).
        describe: a human phrase naming the resource, e.g. ``"resource group 'rg'"``.
        exists: a probe returning True when the resource already exists. Must not
            raise on "absent" — use ``CliTool.exists(...)``, which probes with
            ``check=False``.
        create: the action that creates the resource when ``exists()`` is False.
    """
    if exists():
        ctx.reporter.skip(describe)
        _AUDIT_LOG.info("skipped (exists): %s", describe, extra={"action": "skip", "resource": describe})
    else:
        create()
        ctx.reporter.ok(describe)
        _AUDIT_LOG.info("created: %s", describe, extra={"action": "create", "resource": describe})


def update_if_confirmed(
    ctx: ExecutionContext,
    *,
    describe: str,
    apply: Callable[[], object],
    prompt: str | None = None,
) -> None:
    """Apply a configuration change, asking for confirmation first when asked to.

    Args:
        describe: human phrase naming what is being configured.
        apply: the action that performs the update.
        prompt: when provided, ``ctx.confirm`` is asked and the update is skipped
            if declined. Pass ``None`` (the step's choice, e.g. when the resource
            does not yet exist) to apply without asking.
    """
    if prompt is not None and not ctx.confirm.confirm(prompt):
        ctx.reporter.skip(describe)
        _AUDIT_LOG.info("skipped (declined): %s", describe, extra={"action": "skip", "resource": describe})
        return
    apply()
    ctx.reporter.ok(describe)
    _AUDIT_LOG.info("updated: %s", describe, extra={"action": "update", "resource": describe})


def poll_until(
    ctx: ExecutionContext,
    *,
    describe: str,
    read_state: Callable[[], str],
    done: Collection[str],
    failed: Collection[str] = (),
    timeout: int = 300,
    interval: int = 15,
    sleep: Callable[[float], object] = time.sleep,
) -> str:
    """Poll ``read_state`` until it reports a terminal state.

    Returns the final state once it is in ``done``. Raises `ProvisioError` if the
    state enters ``failed`` or the ``timeout`` elapses. ``sleep`` is injected so
    tests run instantly.
    """
    elapsed = 0
    while True:
        state = read_state()
        if state in done:
            ctx.reporter.ok(describe)
            _AUDIT_LOG.info(
                "ready: %s (%s)", describe, state,
                extra={"action": "poll_done", "resource": describe, "state": state},
            )
            return state
        if state in failed:
            _AUDIT_LOG.info(
                "failed: %s (%s)", describe, state,
                extra={"action": "poll_failed", "resource": describe, "state": state},
            )
            raise ProvisioError(f"{describe}: provisioning ended in state {state!r}")
        if elapsed >= timeout:
            raise ProvisioError(f"{describe}: timed out after {timeout}s (last state {state!r})")
        ctx.reporter.info(f"{describe}: {state} — retrying in {interval}s ({elapsed}s elapsed)")
        sleep(interval)
        elapsed += interval
