"""provisio — compose, test, and audit CLI-driven infrastructure provisioning.

The public API is re-exported here as the framework grows. For now the package
is a skeleton; increments add the command layer, primitives, plan, and CLI.
"""
from importlib.metadata import PackageNotFoundError, version

from provisio.application import CliToolSpec, InfraApplication
from provisio.cli_tool import CliTool
from provisio.command import CommandResult, CommandRunner, SubprocessCommandRunner
from provisio.context import ExecutionContext, OutputKey
from provisio.diff import Diff, diff
from provisio.errors import (
    CommandFailedError,
    ExecutableNotFoundError,
    MissingOutputError,
    ProvisioError,
)
from provisio.interaction import AutoConfirmer, Confirmer, Prompter
from provisio.logging import Redactor, configure_audit_log, get_logger
from provisio.plan import (
    FunctionStep,
    Plan,
    RunResult,
    Step,
    command_step,
    step,
)
from provisio.primitives import ensure, poll_until, update_if_confirmed
from provisio.reporting import ConsoleReporter, NullReporter, Reporter
from provisio.settings import Setting, Settings, resolve_settings
from provisio.state import (
    FileStateStore,
    NullStateStore,
    State,
    StateStore,
    StepState,
)

try:
    # Single source of truth: the version declared in pyproject.toml, read from
    # the installed package metadata rather than duplicated as a literal here.
    __version__ = version("provisio")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
    "CommandResult",
    "CommandRunner",
    "SubprocessCommandRunner",
    "CliTool",
    "ExecutionContext",
    "OutputKey",
    "CommandFailedError",
    "ExecutableNotFoundError",
    "MissingOutputError",
    "ProvisioError",
    "Redactor",
    "get_logger",
    "configure_audit_log",
    "Reporter",
    "NullReporter",
    "ConsoleReporter",
    "Confirmer",
    "Prompter",
    "AutoConfirmer",
    "ensure",
    "update_if_confirmed",
    "poll_until",
    "Step",
    "FunctionStep",
    "step",
    "command_step",
    "Plan",
    "RunResult",
    "Setting",
    "Settings",
    "resolve_settings",
    "InfraApplication",
    "CliToolSpec",
    "State",
    "StepState",
    "StateStore",
    "FileStateStore",
    "NullStateStore",
    "Diff",
    "diff",
    # "build_cli" is available via `from provisio import build_cli` but is not in
    # __all__: it lives in the optional `cli` extra and is imported lazily below,
    # so `import *` never forces click on the dependency-free core.
]


def __getattr__(name: str) -> object:
    """Lazily expose `build_cli` without importing click at core import time."""
    if name == "build_cli":
        from provisio.app_cli import build_cli

        return build_cli
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
