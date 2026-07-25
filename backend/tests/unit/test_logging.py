"""Unit tests for structured JSON logging configuration."""

import json
import logging


def test_configure_logging_emits_json_records(capsys) -> None:  # type: ignore[no-untyped-def]
    """After configure_logging(), a log record is emitted as one JSON object per line."""
    from app.core.logging import configure_logging

    configure_logging(log_level="INFO")
    logger = logging.getLogger("app.test")
    logger.info("hello world")

    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    payload = json.loads(line)

    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert "timestamp" in payload
