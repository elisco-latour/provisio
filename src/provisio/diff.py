"""Declaration diff — the CI re-provisioning gate.

`diff` compares a new plan + resolved settings against the persisted `State` and
reports which steps were added/removed/changed and whether the inputs changed. It
performs no cloud calls and makes no existence claims: it answers only "did our
definition change since the last apply?".
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from provisio.plan import Plan
from provisio.settings import Settings
from provisio.state import State, hash_text


def input_fingerprint(values: Mapping[str, str]) -> str:
    """A stable hash of resolved settings (order-independent, values never raw)."""
    return hash_text(*(f"{name}={values[name]}" for name in sorted(values)))


@dataclass(frozen=True, slots=True)
class Diff:
    """The result of comparing a definition against persisted state."""

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    inputs_changed: bool = False
    is_first_apply: bool = False

    @property
    def is_empty(self) -> bool:
        """True when nothing changed (CI can skip re-provisioning)."""
        return not (
            self.added or self.removed or self.changed or self.inputs_changed or self.is_first_apply
        )


def diff(previous: State | None, plan: Plan, settings: Settings) -> Diff:
    """Compare ``plan`` + ``settings`` against ``previous`` state."""
    current_steps = {s.key: s.fingerprint() for s in plan.steps}

    if previous is None:
        return Diff(added=tuple(current_steps), is_first_apply=True)

    previous_steps = {s.key: s.fingerprint for s in previous.steps}
    added = tuple(key for key in current_steps if key not in previous_steps)
    removed = tuple(key for key in previous_steps if key not in current_steps)
    changed = tuple(
        key
        for key, fp in current_steps.items()
        if key in previous_steps and previous_steps[key] != fp
    )
    inputs_changed = previous.input_fingerprint != input_fingerprint(settings.as_dict())
    return Diff(added=added, removed=removed, changed=changed, inputs_changed=inputs_changed)
