# API reference

Generated from the source docstrings via [mkdocstrings](https://mkdocstrings.github.io/).

## Composition

::: provisio.plan.Plan
::: provisio.plan.step
::: provisio.plan.command_step
::: provisio.plan.RunResult
::: provisio.context.ExecutionContext
::: provisio.context.OutputKey

## Primitives

::: provisio.primitives.ensure
::: provisio.primitives.update_if_confirmed
::: provisio.primitives.poll_until

## Command layer

::: provisio.command.CommandResult
::: provisio.command.CommandRunner
::: provisio.command.SubprocessCommandRunner
::: provisio.cli_tool.CliTool

## Observability

::: provisio.reporting.Reporter
::: provisio.logging.configure_audit_log
::: provisio.logging.Redactor
::: provisio.logging.get_logger

## Settings & application

::: provisio.settings.Setting
::: provisio.settings.resolve_settings
::: provisio.application.InfraApplication
::: provisio.application.CliToolSpec

## State & diff

::: provisio.state.State
::: provisio.state.StateStore
::: provisio.state.FileStateStore
::: provisio.diff.diff
::: provisio.diff.Diff

## Testing utilities

::: provisio.testing.FakeCommandRunner
::: provisio.testing.RecordingReporter
