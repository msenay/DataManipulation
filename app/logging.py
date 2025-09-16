"""Structured logging configuration."""
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from app.config import settings

# Context variables for request-scoped data
tenant_id_ctx: ContextVar[Optional[UUID]] = ContextVar("tenant_id", default=None)
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request context if available
        tenant_id = tenant_id_ctx.get()
        if tenant_id:
            log_data["tenant_id"] = str(tenant_id)

        request_id = request_id_ctx.get()
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname", 
                "filename", "module", "lineno", "funcName", "created", 
                "msecs", "relativeCreated", "thread", "threadName", 
                "processName", "process", "getMessage", "exc_info", 
                "exc_text", "stack_info"
            }:
                log_data[key] = value

        return json.dumps(log_data, default=str, separators=(",", ":"))


def setup_logging() -> None:
    """Configure application logging."""
    # Remove all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with structured formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)