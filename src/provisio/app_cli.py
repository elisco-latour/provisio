"""Generate a Click CLI from an `InfraApplication` — the optional ``cli`` extra.

This is the only module that imports ``click`` (imported lazily via the package's
``__getattr__``, so the core stays dependency-free). Options are derived from the
app's settings schema, so there is one declaration per option — the CLI, the
resolver, and redaction all read the same `Setting`s.

Two commands: ``apply`` (provision + persist state) and ``diff`` (compare the
current definition to persisted state, Terraform-style exit codes).
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from importlib.metadata import version as _package_version
from typing import Any

import click

from provisio.application import InfraApplication
from provisio.cli_tool import CliTool
from provisio.command import SubprocessCommandRunner
from provisio.context import ExecutionContext
from provisio.diff import diff, input_fingerprint
from provisio.errors import ProvisioError
from provisio.interaction import AutoConfirmer
from provisio.logging import Redactor, configure_audit_log
from provisio.plan import RunResult
from provisio.reporting import ConsoleReporter
from provisio.settings import Settings, resolve_settings, secret_values
from provisio.state import FileStateStore, NullStateStore, State, StateStore, StepState, hash_text


class ClickPrompter:
    """A `Prompter` backed by ``click.prompt`` (hidden input for secrets)."""

    def ask(self, label: str, *, default: str | None = None, secret: bool = False) -> str | None:
        return click.prompt(label, default=default, hide_input=secret, show_default=not secret)


class ClickConfirmer:
    """A `Confirmer` backed by ``click.confirm`` (or auto-yes under ``--yes``)."""

    def __init__(self, assume_yes: bool = False) -> None:
        self._assume_yes = assume_yes

    def confirm(self, prompt: str, *, default: bool = False) -> bool:
        if self._assume_yes:
            return True
        return click.confirm(prompt, default=default)


def build_cli(app: InfraApplication) -> click.Group:
    """Build the Click command group for ``app`` (``apply`` + ``diff``)."""
    group = click.Group(name=app.name, help=app.help)
    group.add_command(_apply_command(app))
    group.add_command(_diff_command(app))
    return group


def _setting_options(app: InfraApplication) -> list[click.Parameter]:
    return [click.Option([spec.option_flag], default=None, help=spec.help) for spec in app.settings]


def _state_store(state_path: str | None) -> StateStore:
    return FileStateStore(state_path) if state_path else NullStateStore()


def _apply_command(app: InfraApplication) -> click.Command:
    params = _setting_options(app) + [
        click.Option(["--dry-run"], is_flag=True, help="List the steps that would run, then exit."),
        click.Option(["--skip"], multiple=True, help="Skip a step by key (repeatable)."),
        click.Option(["--yes/--no-yes", "-y"], default=False, help="Skip confirmation prompts (CI mode)."),
        click.Option(["--log-file"], default=None, help="Write the audit log to this file (default: stdout)."),
        click.Option(
            ["--log-format"], type=click.Choice(["text", "json"]), default="text", help="Audit log format."
        ),
        click.Option(["--state"], default=None, help="Path to the state file (default: no state persisted)."),
    ]

    def callback(**kwargs: Any) -> None:
        dry_run = kwargs.pop("dry_run")
        skip = kwargs.pop("skip")
        yes = kwargs.pop("yes")
        log_file = kwargs.pop("log_file")
        log_format = kwargs.pop("log_format")
        state_path = kwargs.pop("state")
        cli_values = {name: value for name, value in kwargs.items() if value is not None}

        if dry_run:
            # Configure the audit log even in dry-run so the preview leaves a
            # compliance trace. No settings are resolved (dry-run needs no creds),
            # so there are no secret values to redact.
            configure_audit_log(destination=log_file or "stdout", fmt=log_format, redactor=Redactor([]))
            app.plan.dry_run(ExecutionContext(reporter=ConsoleReporter()), skip=skip)
            return

        interactive = sys.stdin.isatty() and not yes
        prompter = ClickPrompter() if interactive else None
        confirm = ClickConfirmer(assume_yes=yes) if interactive else AutoConfirmer(True)

        try:
            settings = resolve_settings(app.settings, cli=cli_values, env=os.environ, prompter=prompter)
        except ProvisioError as exc:
            raise click.ClickException(str(exc)) from exc

        configure_audit_log(
            destination=log_file or "stdout",
            fmt=log_format,
            redactor=Redactor(secret_values(app.settings, settings)),
        )

        runner = SubprocessCommandRunner()
        tools: dict[str, CliTool] = {}
        for spec in app.tools:
            if shutil.which(spec.binary_name) is None:
                raise click.ClickException(
                    f"required CLI '{spec.binary_name}' not found on PATH — is it installed?"
                )
            tools[spec.name] = CliTool(
                spec.binary_name, runner, json_flags=spec.json_flags, tsv_flags=spec.tsv_flags
            )

        ctx = ExecutionContext(settings=settings, reporter=ConsoleReporter(), tools=tools, confirm=confirm)
        try:
            result = app.plan.execute(ctx, skip=skip)
        except ProvisioError as exc:
            raise click.ClickException(str(exc)) from exc

        _write_state(app, settings, result, _state_store(state_path))

    return click.Command(
        name="apply", params=params, callback=callback, help="Provision the infrastructure (idempotent)."
    )


def _diff_command(app: InfraApplication) -> click.Command:
    params = _setting_options(app) + [
        click.Option(["--state"], default=None, help="Path to the state file to compare against."),
    ]

    def callback(**kwargs: Any) -> None:
        state_path = kwargs.pop("state")
        cli_values = {name: value for name, value in kwargs.items() if value is not None}

        try:
            settings = resolve_settings(app.settings, cli=cli_values, env=os.environ, prompter=None)
        except ProvisioError as exc:
            raise click.ClickException(str(exc)) from exc

        result = diff(_state_store(state_path).load(), app.plan, settings)

        reporter = ConsoleReporter()
        if result.is_first_apply:
            reporter.info("no previous state — every step is new (first apply)")
        elif result.is_empty:
            reporter.info("no changes since last apply")
        else:
            for key in result.added:
                reporter.info(f"+ {key} (new)")
            for key in result.removed:
                reporter.info(f"- {key} (removed)")
            for key in result.changed:
                reporter.info(f"~ {key} (changed)")
            if result.inputs_changed:
                reporter.info("~ inputs changed")

        # Terraform-style: 0 = no changes, 2 = changes present. (Errors -> 1 via ClickException.)
        if not result.is_empty:
            sys.exit(2)

    return click.Command(
        name="diff",
        params=params,
        callback=callback,
        help="Show what changed since the last apply (exit 2 if there are changes).",
    )


def _write_state(
    app: InfraApplication, settings: Settings, result: RunResult, store: StateStore
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    previous = store.load()
    created_at = previous.created_at if previous else now

    secret_output_names = {key.name for step in app.plan.steps for key in step.produces if key.secret}
    fingerprints = {step.key: step.fingerprint() for step in app.plan.steps}
    outputs = {
        name: (hash_text(value) if name in secret_output_names else value)
        for name, value in result.outputs.items()
    }

    store.save(
        State(
            app_name=app.name,
            provisio_version=_package_version("provisio"),
            plan_fingerprint=app.plan.fingerprint(),
            input_fingerprint=input_fingerprint(settings.as_dict()),
            steps=tuple(
                StepState(sr.key, sr.title, fingerprints[sr.key], sr.status) for sr in result.steps
            ),
            outputs=outputs,
            created_at=created_at,
            updated_at=now,
        )
    )
