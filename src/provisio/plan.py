"""Steps and the Plan that sequences them.

A `Step` is a named unit of work over the `ExecutionContext`. The common case is
a plain function wrapped by `@step` (composition — no template-method base class),
because real steps vary too much to share one shape.

A `Plan` is an explicit, ordered list of steps. The order IS the feature: there is
no DAG auto-ordering, no plugin discovery. Plan validates output wiring up front,
runs steps (honouring skip), emits reporter/audit events, and returns a
`RunResult` so callers can use it as a library, not just via the CLI.
"""
from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from provisio.context import ExecutionContext, OutputKey
from provisio.errors import MissingOutputError, ProvisioError, StepFailedError
from provisio.state import hash_text

_AUDIT_LOG = logging.getLogger("provisio.plan")


@runtime_checkable
class Step(Protocol):
    """A named unit of work with declared output dependencies."""

    key: str
    title: str
    requires: tuple[OutputKey[Any], ...]
    produces: tuple[OutputKey[Any], ...]

    def run(self, ctx: ExecutionContext) -> None: ...
    def fingerprint(self) -> str: ...


@dataclass(frozen=True, slots=True)
class FunctionStep:
    """A `Step` built from a plain ``action(ctx)`` function (via `@step`)."""

    key: str
    title: str
    action: Callable[[ExecutionContext], object]
    requires: tuple[OutputKey[Any], ...] = ()
    produces: tuple[OutputKey[Any], ...] = ()
    # Extra fingerprint material for steps whose behaviour is not visible in the
    # action's source (e.g. command_step, whose argv lives in a closure).
    fingerprint_extra: tuple[str, ...] = ()

    def run(self, ctx: ExecutionContext) -> None:
        self.action(ctx)

    def fingerprint(self) -> str:
        """A stable hash of what this step declares and does.

        Covers key/title/requires/produces, any ``fingerprint_extra``, and the
        action's source. A code edit changes the fingerprint (safe over-report →
        an idempotent re-apply); a step reading changed *external* data with no
        code/input change is not detected (that is out-of-band drift, out of scope).
        """
        try:
            source = inspect.getsource(self.action)
        except (OSError, TypeError):  # pragma: no cover - source unavailable (e.g. REPL)
            source = repr(self.action)
        return hash_text(
            self.key,
            self.title,
            ",".join(k.name for k in self.requires),
            ",".join(k.name for k in self.produces),
            *self.fingerprint_extra,
            source,
        )


def step(
    key: str,
    title: str,
    *,
    requires: Collection[OutputKey[Any]] = (),
    produces: Collection[OutputKey[Any]] = (),
) -> Callable[[Callable[[ExecutionContext], object]], FunctionStep]:
    """Decorator turning an ``action(ctx)`` function into a `FunctionStep`.

    ``requires``/``produces`` declare the output data-flow: they are validated up
    front by `Plan` and are the source of the (deferred) dependency graph.
    """

    def decorate(action: Callable[[ExecutionContext], object]) -> FunctionStep:
        return FunctionStep(key, title, action, tuple(requires), tuple(produces))

    return decorate


def command_step(key: str, title: str, tool: str, *args: str) -> FunctionStep:
    """Wrap a single CLI command as a step — the L1 adoption on-ramp.

    No idempotency: it just runs ``tool args`` (audited, previewable, ordered).
    Add an ``exists=`` probe via `ensure` later to reach L2.
    """

    def action(ctx: ExecutionContext) -> None:
        ctx.tool(tool)(*args)

    return FunctionStep(key, title, action, fingerprint_extra=(tool, *args))


@dataclass(frozen=True, slots=True)
class StepResult:
    """Per-step outcome recorded in a `RunResult`."""

    key: str
    title: str
    status: Literal["ran", "skipped"]


@dataclass(frozen=True, slots=True)
class RunResult:
    """The programmatic result of executing a plan (the library entry point)."""

    steps: tuple[StepResult, ...]
    outputs: dict[str, Any]

    @property
    def ok(self) -> bool:
        # execute() raises on failure, so a returned RunResult is always ok; this
        # stays for symmetry and future continue-on-error modes.
        return True


@dataclass(frozen=True, slots=True)
class PreviewLine:
    """One line of a dry-run preview."""

    index: int
    total: int
    title: str
    skipped: bool
    key: str = ""

    def render(self) -> str:
        suffix = " (skipped)" if self.skipped else ""
        return f"[{self.index}/{self.total}] {self.title}{suffix}"


@dataclass
class Plan:
    """An explicit, ordered sequence of steps."""

    steps: list[Step]

    def validate(self) -> None:
        """Statically check that every `requires` is produced by an earlier step.

        Ignores skip (that is a runtime concern); this catches a malformed plan
        before any command runs.
        """
        produced: set[str] = set()
        for current in self.steps:
            for required in current.requires:
                if required.name not in produced:
                    raise MissingOutputError(
                        f"{required.name!r} required by step {current.key!r} "
                        f"is not produced by any earlier step"
                    )
            produced.update(p.name for p in current.produces)

    def preview(self, skip: Collection[str] = ()) -> list[PreviewLine]:
        """Return the ordered preview lines, marking ``skip``ped steps."""
        total = len(self.steps)
        return [
            PreviewLine(index=i, total=total, title=s.title, skipped=s.key in skip, key=s.key)
            for i, s in enumerate(self.steps, start=1)
        ]

    def dry_run(self, ctx: ExecutionContext, *, skip: Collection[str] = ()) -> list[PreviewLine]:
        """Preview the plan without executing anything.

        Reports each step to ``ctx.reporter`` (the human preview) **and** writes an
        auditable record to the audit log — ``dry-run`` plus ``would-run`` /
        ``would-skip`` per step — so a preview leaves a compliance trace just like a
        real apply. No commands run and no credentials are needed.
        """
        lines = self.preview(skip=skip)
        _AUDIT_LOG.info(
            "dry-run: %d steps", len(self.steps), extra={"action": "dry-run", "steps": len(self.steps)}
        )
        for line in lines:
            ctx.reporter.info(line.render())
            outcome = "would-skip" if line.skipped else "would-run"
            _AUDIT_LOG.info(
                "%s: %s", outcome, line.title, extra={"action": outcome, "step": line.key}
            )
        return lines

    def fingerprint(self) -> str:
        """A hash over the ordered step fingerprints (the plan's structure)."""
        return hash_text(*(s.fingerprint() for s in self.steps))

    def dependency_edges(self) -> list[tuple[str, str]]:
        """(producer_key, consumer_key) edges via OutputKeys — the DAG data."""
        producer_of: dict[str, str] = {}
        edges: list[tuple[str, str]] = []
        for current in self.steps:
            for required in current.requires:
                if required.name in producer_of:
                    edges.append((producer_of[required.name], current.key))
            for produced in current.produces:
                producer_of[produced.name] = current.key
        return edges

    def execute(self, ctx: ExecutionContext, *, skip: Collection[str] = ()) -> RunResult:
        """Run the plan against ``ctx`` and return a `RunResult`.

        Raises `MissingOutputError` if a running step needs an output that a
        skipped step would have produced, `StepFailedError` for unexpected step
        errors, or the original `ProvisioError` for domain failures.
        """
        self.validate()
        results: list[StepResult] = []
        total = len(self.steps)

        for index, current in enumerate(self.steps, start=1):
            ctx.reporter.step(index, total, current.title)

            if current.key in skip:
                ctx.reporter.skip(f"skipped (--skip {current.key})")
                results.append(StepResult(current.key, current.title, "skipped"))
                continue

            missing = [r.name for r in current.requires if not ctx.has(r)]
            if missing:
                raise MissingOutputError(
                    f"{missing} required by step {current.key!r} (was a producing step skipped?)"
                )

            _AUDIT_LOG.info(
                "step %d/%d: %s", index, total, current.title,
                extra={"action": "step", "step": current.key},
            )
            try:
                current.run(ctx)
            except ProvisioError:
                _AUDIT_LOG.error("step failed: %s", current.key, extra={"step": current.key})
                raise
            except Exception as exc:
                _AUDIT_LOG.error("step failed: %s", current.key, extra={"step": current.key})
                raise StepFailedError(current.key, exc) from exc

            results.append(StepResult(current.key, current.title, "ran"))

        return RunResult(steps=tuple(results), outputs=ctx.snapshot())
