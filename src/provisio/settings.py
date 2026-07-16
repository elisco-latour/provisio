"""Declarative settings schema + resolution.

An application declares each option **once** as a `Setting`. That single schema is
the source of truth for three things: how a value is resolved (here), how the CLI
exposes it (app_cli.py), and which values are secret (redaction). This removes the
legacy CLI's duplicate declaration of every option in both a dataclass and the
typer command signature.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from provisio.errors import ProvisioError
from provisio.interaction import Prompter


@dataclass(frozen=True, slots=True)
class Setting:
    """One configurable option, declared once.

    Args:
        name: the resolved attribute name (e.g. ``"resource_group"``).
        env: environment variable to read as a fallback (e.g. ``"AZURE_RESOURCE_GROUP"``).
        default: value used when nothing else is provided (``None`` => required).
        secret: if True, prompted hidden and masked in the audit log.
        help: human description (shown in prompts and generated CLI help).
        flag: CLI flag override; defaults to ``--<name-with-dashes>``.
    """

    name: str
    env: str | None = None
    default: str | None = None
    secret: bool = False
    help: str = ""
    flag: str | None = None

    @property
    def option_flag(self) -> str:
        return self.flag or f"--{self.name.replace('_', '-')}"


class Settings:
    """Resolved settings values with attribute and item access.

    ``settings.resource_group`` and ``settings["resource_group"]`` both work; a
    missing name raises `AttributeError`/`KeyError` respectively.
    """

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def __getattr__(self, name: str) -> str:
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, name: str) -> str:
        return self._values[name]

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name, default)

    def as_dict(self) -> dict[str, str]:
        """A copy of the resolved name->value mapping (used for the input fingerprint)."""
        return dict(self._values)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Settings({sorted(self._values)})"


def resolve_settings(
    specs: Sequence[Setting],
    *,
    cli: Mapping[str, Any],
    env: Mapping[str, str],
    prompter: Prompter | None = None,
) -> Settings:
    """Resolve each `Setting` to a value.

    Precedence: explicit CLI value → environment variable → (interactive prompt |
    default). A required setting (no default) that is not supplied raises
    `ProvisioError` in non-interactive mode.

    Args:
        specs: the settings schema.
        cli: mapping of ``name -> value`` from the CLI (missing => not supplied).
        env: environment mapping (usually ``os.environ``).
        prompter: when provided, missing values are prompted (interactive mode);
            when ``None``, the run is non-interactive (CI).
    """
    resolved: dict[str, str] = {}
    for spec in specs:
        supplied = cli.get(spec.name)
        if supplied is None and spec.env:
            supplied = env.get(spec.env)
        if supplied is not None and str(supplied).strip():
            resolved[spec.name] = str(supplied).strip()
            continue

        if prompter is not None:
            answer = prompter.ask(spec.help or spec.name, default=spec.default, secret=spec.secret)
            answer = (answer or "").strip() or (spec.default or "")
            if not answer:
                raise ProvisioError(f"required setting {spec.name!r} was not provided")
            resolved[spec.name] = answer
            continue

        if spec.default is not None:
            resolved[spec.name] = spec.default
            continue

        raise ProvisioError(
            f"required setting {spec.name!r} not provided; pass {spec.option_flag}"
            + (f" or set {spec.env}" if spec.env else "")
        )

    return Settings(resolved)


def secret_values(specs: Sequence[Setting], settings: Settings) -> list[str]:
    """Return the resolved values of the secret settings (to feed a `Redactor`)."""
    values = []
    for spec in specs:
        if spec.secret:
            value = settings.get(spec.name)
            if value:
                values.append(value)
    return values
