"""Increment 5 — compliance audit logging via stdlib logging, with redaction.

The audit log is the compliance artifact (distinct from console UX). It is a
namespaced stdlib logger so consumers can reuse it anywhere, the CLI chooses the
destination (stdout or a file) and format (text/json), and secrets are masked by
a Redactor before any line is written.
"""
import json

from provisio import Redactor, configure_audit_log, get_logger


def test_redactor_masks_secret_values() -> None:
    redactor = Redactor(["s3cr3t"])
    assert redactor.redact("token=s3cr3t done") == "token=*** done"


def test_redactor_ignores_empty_secrets() -> None:
    redactor = Redactor(["", "  "])
    assert redactor.redact("nothing to hide") == "nothing to hide"


def test_get_logger_is_under_provisio_namespace() -> None:
    assert get_logger().name == "provisio"
    assert get_logger("provisio.command").name == "provisio.command"


def test_configure_writes_text_to_file(tmp_path) -> None:
    log_file = tmp_path / "audit.log"
    logger = configure_audit_log(destination=log_file, fmt="text")
    logger.info("resource group created")
    for handler in logger.handlers:
        handler.flush()
    assert "resource group created" in log_file.read_text()


def test_json_format_emits_structured_fields(tmp_path) -> None:
    log_file = tmp_path / "audit.json"
    logger = configure_audit_log(destination=log_file, fmt="json")
    logger.info("command done", extra={"command": "az group show", "exit_code": 0})
    for handler in logger.handlers:
        handler.flush()
    record = json.loads(log_file.read_text().strip().splitlines()[-1])
    assert record["message"] == "command done"
    assert record["level"] == "INFO"
    assert record["command"] == "az group show"
    assert record["exit_code"] == 0


def test_redaction_applied_to_written_output(tmp_path) -> None:
    log_file = tmp_path / "redacted.log"
    logger = configure_audit_log(destination=log_file, fmt="text", redactor=Redactor(["p@ss"]))
    logger.info("connecting with p@ss now")
    for handler in logger.handlers:
        handler.flush()
    written = log_file.read_text()
    assert "p@ss" not in written
    assert "***" in written


def test_reconfigure_does_not_duplicate_handlers(tmp_path) -> None:
    configure_audit_log(destination=tmp_path / "a.log", fmt="text")
    logger = configure_audit_log(destination=tmp_path / "b.log", fmt="text")
    provisio_handlers = [h for h in logger.handlers if getattr(h, "_provisio_managed", False)]
    assert len(provisio_handlers) == 1
