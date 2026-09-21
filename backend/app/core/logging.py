import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.redaction import redact_text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()) or "",
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            # Tracebacks routinely embed request headers and DSNs; never log them verbatim.
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str, log_file: str | None = None) -> None:
    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [stream_handler]
    if log_file:
        destination = Path(log_file)
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(destination, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level.upper())
