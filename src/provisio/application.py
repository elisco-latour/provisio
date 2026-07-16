"""The application description: what an app declares to become a CLI.

`InfraApplication` is plain data (no click here — this stays in the dependency-free
core): a name/help, the `Plan`, the settings schema, and the CLI tools it uses.
`build_cli` (in app_cli.py, the optional `cli` extra) turns it into a Click CLI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from provisio.plan import Plan
from provisio.settings import Setting


@dataclass(frozen=True, slots=True)
class CliToolSpec:
    """Declares a vendor CLI the app drives (e.g. ``az``, ``gh``).

    ``build_cli`` verifies ``binary_name`` is on PATH before running, then builds
    a `CliTool` registered under ``name`` on the context.
    """

    name: str
    binary: str = ""
    json_flags: tuple[str, ...] = ()
    tsv_flags: tuple[str, ...] = ()

    @property
    def binary_name(self) -> str:
        return self.binary or self.name


@dataclass(frozen=True, slots=True)
class InfraApplication:
    """Everything needed to generate an app's CLI and run its plan."""

    name: str
    help: str
    plan: Plan
    settings: tuple[Setting, ...] = ()
    tools: tuple[CliToolSpec, ...] = field(default_factory=tuple)
