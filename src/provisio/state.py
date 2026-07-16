"""State persistence — the declaration-level record used for the CI diff gate.

We have no resource model, so state is NOT Terraform-style cloud state. It records
what *we declared and last applied*: the plan/input fingerprints, per-step status,
and produced outputs. Diffing a new definition against it (see diff.py) answers
"did our infrastructure definition change?" — enough to gate re-provisioning in CI.

Secrets are never stored raw: inputs are captured only as a fingerprint hash, and
secret-flagged outputs are hashed when the state is built (see the apply command).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

STATE_SCHEMA_VERSION = 1


def hash_text(*parts: str) -> str:
    """A short, stable fingerprint of the given parts.

    Used for step/plan/input fingerprints. Because it is a one-way hash, storing
    it never exposes the underlying values (e.g. secret inputs).
    """
    joined = " ".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class StepState:
    """The recorded outcome + fingerprint of one step at last apply."""

    key: str
    title: str
    fingerprint: str
    status: str


@dataclass(frozen=True, slots=True)
class State:
    """The last-applied declaration snapshot."""

    app_name: str
    provisio_version: str
    plan_fingerprint: str
    input_fingerprint: str
    steps: tuple[StepState, ...]
    outputs: dict[str, str]
    created_at: str
    updated_at: str
    schema_version: int = STATE_SCHEMA_VERSION

    def to_json(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "app_name": self.app_name,
            "provisio_version": self.provisio_version,
            "plan_fingerprint": self.plan_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "steps": [asdict(step) for step in self.steps],
            "outputs": self.outputs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return json.dumps(payload, indent=2)

    @classmethod
    def from_json(cls, text: str) -> State:
        data = json.loads(text)
        return cls(
            app_name=data["app_name"],
            provisio_version=data["provisio_version"],
            plan_fingerprint=data["plan_fingerprint"],
            input_fingerprint=data["input_fingerprint"],
            steps=tuple(StepState(**step) for step in data["steps"]),
            outputs=dict(data["outputs"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            schema_version=data.get("schema_version", STATE_SCHEMA_VERSION),
        )


@runtime_checkable
class StateStore(Protocol):
    """Loads/saves the last-applied `State`. Pluggable (local file default)."""

    def load(self) -> State | None: ...
    def save(self, state: State) -> None: ...


class FileStateStore:
    """Persists state as human-readable JSON on the local filesystem."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)

    def load(self) -> State | None:
        if not self._path.exists():
            return None
        return State.from_json(self._path.read_text(encoding="utf-8"))

    def save(self, state: State) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(state.to_json(), encoding="utf-8")


class NullStateStore:
    """A no-op store: nothing is persisted (the default when state is disabled)."""

    def load(self) -> State | None:
        return None

    def save(self, state: State) -> None:
        return None
