"""Structured JSON logging, configured once for the whole application.

Every later module logs via `logging.getLogger(__name__)` and inherits this
formatting — no module reinvents logging setup. Never logs secrets, passwords, or
full request bodies (see docs/Architecture.md#security-baseline).
"""

import datetime
import json
import logging


class JsonFormatter(logging.Formatter):
    """Renders each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as a JSON string with timestamp, level, logger, and message."""
        payload = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure the root logger to emit JSON records to stderr at the given level."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
