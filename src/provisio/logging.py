"""Compliance audit logging.

This is deliberately thin over the standard library `logging` module: the audit
log is a namespaced stdlib logger (``provisio`` and sub-loggers like
``provisio.command``), so consumers can reuse it anywhere with
``logging.getLogger("provisio")`` and route it however they already route logs.

`configure_audit_log` is what the generated CLI calls to pick a destination
(stdout or a file) and a format (human ``text`` or machine ``json`` for SIEM
ingestion). A `Redactor` masks secret values before any line is written — a
tested invariant, since secrets are passed to CLIs as argv.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

_ROOT_LOGGER_NAME = "provisio"

# Attributes that already exist on every LogRecord; anything else attached via
# ``logger.info(..., extra={...})`` is treated as a structured audit field.
_RESERVED_LOGRECORD_KEYS = set(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


class Redactor:
    """Masks known secret values in any string before it is logged.

    Fed from the settings schema's ``secret=True`` fields (wired later); here it
    is just an ordered set of literal secrets and a mask token. Empty/blank
    secrets are ignored so an unset secret never blanks out unrelated text.
    """

    def __init__(self, secrets: Iterable[str] = (), *, mask: str = "***") -> None:
        self._mask = mask
        self._secrets: list[str] = []
        for secret in secrets:
            self.add(secret)

    def add(self, secret: str) -> None:
        if secret and secret.strip():
            self._secrets.append(secret)

    def redact(self, text: str) -> str:
        # Longest-first so a secret that contains another is masked whole.
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, self._mask)
        return text


class _JsonFormatter(logging.Formatter):
    """Formats each record as a single JSON object (one line)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOGRECORD_KEYS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


class _RedactingFormatter(logging.Formatter):
    """Wraps another formatter and redacts secrets from its output."""

    def __init__(self, inner: logging.Formatter, redactor: Redactor) -> None:
        super().__init__()
        self._inner = inner
        self._redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        return self._redactor.redact(self._inner.format(record))


def get_logger(name: str = _ROOT_LOGGER_NAME) -> logging.Logger:
    """Return a provisio audit logger. Reusable by consumers for their own code.

    Pass a dotted child name (e.g. ``"provisio.command"`` or
    ``"provisio.myapp"``) to log under the provisio namespace.
    """
    return logging.getLogger(name)


def configure_audit_log(
    *,
    destination: str | os.PathLike[str] = "stdout",
    fmt: Literal["text", "json"] = "text",
    redactor: Redactor | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Attach a single audit handler to the ``provisio`` logger and return it.

    Idempotent: re-calling replaces provisio's own handler rather than stacking
    handlers, so repeated configuration (e.g. across CLI invocations or tests)
    does not duplicate output.

    Args:
        destination: ``"stdout"``, ``"stderr"``, or a file path.
        fmt: ``"text"`` (human) or ``"json"`` (structured, for log ingestion).
        redactor: masks secret values in every line when provided.
        level: minimum level to emit (INFO captures the audit trail).
    """
    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, "_provisio_managed", False):
            logger.removeHandler(handler)
            handler.close()

    handler = _make_handler(destination)
    handler._provisio_managed = True  # type: ignore[attr-defined]
    base: logging.Formatter = (
        _JsonFormatter()
        if fmt == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler.setFormatter(_RedactingFormatter(base, redactor) if redactor else base)
    logger.addHandler(handler)
    return logger


def _make_handler(destination: str | os.PathLike[str]) -> logging.Handler:
    if destination == "stdout":
        return logging.StreamHandler(sys.stdout)
    if destination == "stderr":
        return logging.StreamHandler(sys.stderr)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    return logging.FileHandler(path, encoding="utf-8")
