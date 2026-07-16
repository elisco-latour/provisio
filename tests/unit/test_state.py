"""Increment 15 — the state persistence layer.

State records the last-applied plan/input fingerprints, per-step status, and
produced outputs. A pluggable StateStore persists it (local JSON by default);
the diff against it (next increment) is the CI re-provisioning gate.
"""
from provisio.state import FileStateStore, NullStateStore, State, StateStore, StepState


def _sample() -> State:
    return State(
        app_name="demo",
        provisio_version="0.1.0",
        plan_fingerprint="plan-abc",
        input_fingerprint="input-def",
        steps=(StepState(key="rg", title="Resource group", fingerprint="fp1", status="ran"),),
        outputs={"subscription_id": "sub-123"},
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def test_file_store_is_a_statestore(tmp_path) -> None:
    assert isinstance(FileStateStore(tmp_path / "state.json"), StateStore)


def test_file_store_returns_none_when_absent(tmp_path) -> None:
    assert FileStateStore(tmp_path / "missing.json").load() is None


def test_file_store_roundtrip(tmp_path) -> None:
    store = FileStateStore(tmp_path / "state.json")
    state = _sample()
    store.save(state)
    assert store.load() == state


def test_null_store_never_persists() -> None:
    store = NullStateStore()
    store.save(_sample())
    assert store.load() is None


def test_state_json_is_human_readable(tmp_path) -> None:
    path = tmp_path / "state.json"
    FileStateStore(path).save(_sample())
    text = path.read_text(encoding="utf-8")
    assert '"app_name": "demo"' in text
    assert '"plan_fingerprint": "plan-abc"' in text
    assert '"subscription_id": "sub-123"' in text
