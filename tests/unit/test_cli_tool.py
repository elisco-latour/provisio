"""Increment 8 — CliTool: the generic vendor-CLI facade.

`az`, `gh`, `gcloud`, `aws` are all just CliTool instances over the same runner.
The only per-CLI knowledge is the binary name and the flags that request JSON/TSV
output — configured, never assumed. This is where CLI specifics are quarantined,
which is what keeps the rest of provisio cloud-agnostic.
"""
import pytest

from provisio import CliTool, ProvisioError
from provisio.testing import FakeCommandRunner


def test_call_prepends_binary_to_argv() -> None:
    fake = FakeCommandRunner()
    az = CliTool("az", fake)
    az("group", "show", "--name", "rg")
    assert fake.calls == [("az", "group", "show", "--name", "rg")]


def test_call_returns_stripped_stdout() -> None:
    fake = FakeCommandRunner().stub("az", "account", "show", stdout="  sub-1\n")
    az = CliTool("az", fake)
    assert az("account", "show") == "sub-1"


def test_exists_true_when_probe_succeeds() -> None:
    az = CliTool("az", FakeCommandRunner())  # unmatched calls default to success
    assert az.exists("group", "show", "--name", "rg") is True


def test_exists_false_and_does_not_raise_when_probe_fails() -> None:
    fake = FakeCommandRunner().stub("az", "group", "show", returncode=3)
    az = CliTool("az", fake)
    # would raise CommandFailedError if it used check=True; exists must not.
    assert az.exists("group", "show", "--name", "nope") is False


def test_json_appends_configured_flags_and_parses() -> None:
    fake = FakeCommandRunner().stub("az", "group", "show", stdout='{"id": "x"}')
    az = CliTool("az", fake, json_flags=("-o", "json"))
    assert az.json("group", "show", "--name", "rg") == {"id": "x"}
    assert fake.calls[-1] == ("az", "group", "show", "--name", "rg", "-o", "json")


def test_tsv_appends_configured_flags() -> None:
    fake = FakeCommandRunner().stub("az", "account", "show", stdout="sub-1\n")
    az = CliTool("az", fake, tsv_flags=("-o", "tsv"))
    assert az.tsv("account", "show", "--query", "id") == "sub-1"
    assert fake.calls[-1] == ("az", "account", "show", "--query", "id", "-o", "tsv")


def test_json_without_configured_flags_raises() -> None:
    az = CliTool("az", FakeCommandRunner())
    with pytest.raises(ProvisioError):
        az.json("group", "show")


def test_cloud_agnostic_flags_differ_per_binary() -> None:
    # Proof the facade isn't Azure-bound: gcloud uses --format=json, az uses -o json.
    fake = FakeCommandRunner().stub("gcloud", stdout="{}")
    gcloud = CliTool("gcloud", fake, json_flags=("--format=json",))
    gcloud.json("compute", "instances", "list")
    assert fake.calls[-1] == ("gcloud", "compute", "instances", "list", "--format=json")
