"""Increment 13 — declarative Settings schema + resolution.

Each option is declared once as a `Setting` (name/env/default/secret/help). That
single schema drives resolution now, and CLI generation + redaction next — killing
the legacy CLI's double declaration (dataclass AND the typer signature).
"""
import pytest

from provisio import ProvisioError, Setting, Settings, resolve_settings
from provisio.settings import secret_values
from provisio.testing import FakePrompter

RG = Setting("resource_group", env="AZURE_RESOURCE_GROUP", default="demo-rg", help="Resource group")
KEY = Setting("openai_key", env="AZURE_OPENAI_API_KEY", secret=True, help="Azure OpenAI API key")


def test_cli_value_wins_over_env_and_default() -> None:
    settings = resolve_settings([RG], cli={"resource_group": "cli-rg"}, env={"AZURE_RESOURCE_GROUP": "env-rg"})
    assert settings.resource_group == "cli-rg"


def test_env_used_when_no_cli_value() -> None:
    settings = resolve_settings([RG], cli={}, env={"AZURE_RESOURCE_GROUP": "env-rg"})
    assert settings.resource_group == "env-rg"


def test_default_used_when_non_interactive() -> None:
    settings = resolve_settings([RG], cli={}, env={})
    assert settings.resource_group == "demo-rg"


def test_missing_required_non_interactive_errors() -> None:
    with pytest.raises(ProvisioError):
        resolve_settings([KEY], cli={}, env={})


def test_prompts_when_interactive_and_missing() -> None:
    prompter = FakePrompter(["typed-key"])
    settings = resolve_settings([KEY], cli={}, env={}, prompter=prompter)
    assert settings.openai_key == "typed-key"
    assert prompter.asked[0][1] is True  # asked as a secret


def test_option_flag_is_derived_from_name() -> None:
    assert RG.option_flag == "--resource-group"
    assert Setting("openai_key", flag="--openai-key").option_flag == "--openai-key"


def test_settings_attribute_and_item_access() -> None:
    settings = Settings({"a": "1"})
    assert settings.a == "1"
    assert settings["a"] == "1"


def test_missing_attribute_raises_attributeerror() -> None:
    settings = Settings({"a": "1"})
    with pytest.raises(AttributeError):
        _ = settings.nope


def test_secret_values_collects_only_secrets() -> None:
    settings = resolve_settings([RG, KEY], cli={"openai_key": "sk-xyz"}, env={})
    assert secret_values([RG, KEY], settings) == ["sk-xyz"]
