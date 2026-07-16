"""The execution context: typed output-threading + the collaborator bag.

Every step receives an `ExecutionContext`. It carries the CLI tools, the reporter,
the resolved settings, and the outputs produced so far — so a step is configured
entirely by what is injected (composition), never by module-level globals.

`OutputKey[T]` replaces the legacy CLI's fragile string-keyed value-threading
(a connascence-of-name hotspot) with a single, typed definition site.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from provisio.cli_tool import CliTool
from provisio.errors import MissingOutputError, ProvisioError
from provisio.interaction import AutoConfirmer, Confirmer
from provisio.reporting import NullReporter, Reporter


@dataclass(frozen=True, slots=True)
class OutputKey[T]:
    """A typed handle for a value one step produces and another consumes.

    Declare each key once (e.g. ``SWA_URL: OutputKey[str] = OutputKey("swa_url")``)
    and pass the key — not a bare string — to ``ctx.set``/``ctx.get``. The type
    parameter flows through ``get`` so consumers get the right static type.

    Mark ``secret=True`` for sensitive values (e.g. deploy tokens): they are
    hashed, never stored raw, when a run is persisted to state.
    """

    name: str
    secret: bool = False


@dataclass
class ExecutionContext:
    """Collaborators + produced outputs, handed to every step.

    Defaults are deliberately sensible so the minimal path stays short (see the
    simplicity budget): a silent `NullReporter` and an empty tool registry.
    """

    settings: Any = None
    reporter: Reporter = field(default_factory=NullReporter)
    tools: dict[str, CliTool] = field(default_factory=dict)
    # Defaults to auto-yes: the sensible non-interactive behaviour. The CLI wires
    # an interactive confirmer (or AutoConfirmer(False)) as appropriate.
    confirm: Confirmer = field(default_factory=lambda: AutoConfirmer(True))
    _outputs: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def tool(self, name: str) -> CliTool:
        """Return the registered CLI tool, or raise a clear error if absent."""
        try:
            return self.tools[name]
        except KeyError:
            raise ProvisioError(f"no CLI tool named {name!r} is registered on the context") from None

    def set[T](self, key: OutputKey[T], value: T) -> None:
        """Record the value produced for ``key``."""
        self._outputs[key.name] = value

    def get[T](self, key: OutputKey[T]) -> T:
        """Return the value produced for ``key``, or raise `MissingOutputError`."""
        try:
            return self._outputs[key.name]
        except KeyError:
            raise MissingOutputError(key.name) from None

    def has(self, key: OutputKey[Any]) -> bool:
        """True if a value has been produced for ``key``."""
        return key.name in self._outputs

    def snapshot(self) -> dict[str, Any]:
        """A copy of the produced outputs, keyed by name (for `RunResult`)."""
        return dict(self._outputs)
