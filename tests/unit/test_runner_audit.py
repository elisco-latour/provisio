"""Increment 6 — the real runner writes an audit record for every command.

Full command traceability is the compliance backbone: each executed command and
its exit code lands in the audit log, and secrets in the argv are redacted.
"""
import json
import sys

from provisio import Redactor, SubprocessCommandRunner, configure_audit_log, get_logger


def _flush() -> None:
    for handler in get_logger().handlers:
        handler.flush()


def test_runner_logs_command_and_exit_code(tmp_path) -> None:
    log_file = tmp_path / "audit.json"
    configure_audit_log(destination=log_file, fmt="json")

    SubprocessCommandRunner().run([sys.executable, "-c", "pass"])
    _flush()

    records = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    command_records = [r for r in records if "exit_code" in r]
    assert command_records, "expected an audit record with an exit_code"
    assert command_records[-1]["exit_code"] == 0
    assert "-c" in command_records[-1]["command"]


def test_runner_logs_failure_exit_code(tmp_path) -> None:
    log_file = tmp_path / "audit.json"
    configure_audit_log(destination=log_file, fmt="json")

    SubprocessCommandRunner().run([sys.executable, "-c", "import sys; sys.exit(4)"], check=False)
    _flush()

    records = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    assert records[-1]["exit_code"] == 4


def test_runner_redacts_secret_in_audit(tmp_path) -> None:
    log_file = tmp_path / "audit.log"
    configure_audit_log(destination=log_file, fmt="text", redactor=Redactor(["SUPERSECRET"]))

    SubprocessCommandRunner().run([sys.executable, "-c", "pass", "SUPERSECRET"])
    _flush()

    written = log_file.read_text()
    assert "SUPERSECRET" not in written
    assert "***" in written
