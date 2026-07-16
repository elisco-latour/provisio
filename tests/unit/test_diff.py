"""Increment 16 — fingerprints and the declaration diff.

Fingerprints are deterministic hashes of what was declared (step structure +
action source; inputs). `diff` compares a new plan+settings against persisted
state to answer "did our definition change?" — the CI re-provisioning gate.
"""
from provisio import ExecutionContext, Plan, Setting, resolve_settings, step
from provisio.diff import Diff, diff, input_fingerprint
from provisio.settings import Settings
from provisio.state import State, StepState


def _noop(ctx: ExecutionContext) -> None:
    """Stable, named action so fingerprints depend only on declarations."""


def _state_matching(app: str, plan: Plan, settings: Settings) -> State:
    return State(
        app_name=app,
        provisio_version="0",
        plan_fingerprint=plan.fingerprint(),
        input_fingerprint=input_fingerprint(settings.as_dict()),
        steps=tuple(StepState(s.key, s.title, s.fingerprint(), "ran") for s in plan.steps),
        outputs={},
        created_at="t",
        updated_at="t",
    )


def test_step_fingerprint_is_deterministic() -> None:
    a = Plan([step("a", "A")(_noop)])
    b = Plan([step("a", "A")(_noop)])
    assert a.steps[0].fingerprint() == b.steps[0].fingerprint()


def test_plan_fingerprint_changes_when_a_step_is_added() -> None:
    one = Plan([step("a", "A")(_noop)])
    two = Plan([step("a", "A")(_noop), step("b", "B")(_noop)])
    assert one.fingerprint() != two.fingerprint()


def test_input_fingerprint_changes_with_value_and_is_not_raw() -> None:
    one = input_fingerprint({"openai_key": "secret-A"})
    two = input_fingerprint({"openai_key": "secret-B"})
    assert one != two
    assert "secret-A" not in one  # a hash, never the raw value


def test_diff_reports_first_apply_when_no_previous_state() -> None:
    settings = resolve_settings([], cli={}, env={})
    result = diff(None, Plan([step("a", "A")(_noop)]), settings)
    assert result.is_first_apply
    assert not result.is_empty


def test_diff_is_empty_when_nothing_changed() -> None:
    settings = resolve_settings([], cli={}, env={})
    plan = Plan([step("a", "A")(_noop), step("b", "B")(_noop)])
    previous = _state_matching("demo", plan, settings)
    assert diff(previous, plan, settings).is_empty


def test_diff_detects_added_removed_and_changed_steps() -> None:
    settings = resolve_settings([], cli={}, env={})
    previous = _state_matching(
        "demo",
        Plan([step("a", "A")(_noop), step("b", "B")(_noop), step("c", "C")(_noop)]),
        settings,
    )
    current = Plan(
        [
            step("a", "A")(_noop),
            step("b", "B changed")(_noop),  # title change -> fingerprint change
            step("d", "D")(_noop),
        ]
    )
    result: Diff = diff(previous, current, settings)
    assert set(result.added) == {"d"}
    assert set(result.removed) == {"c"}
    assert set(result.changed) == {"b"}
    assert not result.is_empty


def test_diff_detects_input_change_without_exposing_values() -> None:
    specs = [Setting("region", default="eastus")]
    plan = Plan([step("a", "A")(_noop)])
    previous = _state_matching("demo", plan, resolve_settings(specs, cli={"region": "eastus"}, env={}))
    result = diff(previous, plan, resolve_settings(specs, cli={"region": "westus"}, env={}))
    assert result.inputs_changed
    assert not result.is_empty
