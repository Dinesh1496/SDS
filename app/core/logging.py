"""
Centralised logging configuration using Loguru.

Provides structured JSON logging for production and human-readable
text output for development. All modules import the logger from here
to ensure consistent formatting, correlation IDs, and log routing.

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Operation completed", records_processed=42)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Intercept handler — routes stdlib logging into Loguru
# ---------------------------------------------------------------------------

class _InterceptHandler(logging.Handler):
    """
    Intercept standard library log records and re-emit via Loguru.

    This ensures that third-party libraries (SQLAlchemy, uvicorn, httpx, etc.)
    that use stdlib logging are also captured and formatted consistently.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Map stdlib level to Loguru level name
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Walk the call stack to find the originating frame (outside Loguru)
        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ---------------------------------------------------------------------------
# JSON serialiser for Loguru
# ---------------------------------------------------------------------------

def _json_serializer(record: dict[str, Any]) -> str:
    """
    Produce a structured JSON log line from a Loguru record.

    Fields emitted:
      timestamp, level, logger (name), message, module, function, line,
      thread, process, and any extra bound values.
    """
    import json

    subset: dict[str, Any] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "thread": record["thread"].id,
        "process": record["process"].id,
    }

    # Merge any extra key/value pairs bound via logger.bind(...)
    subset.update(record["extra"])

    # Attach exception info if present
    if record["exception"]:
        exc = record["exception"]
        subset["exception"] = {
            "type": exc.type.__name__ if exc.type else None,
            "value": str(exc.value) if exc.value else None,
        }

    return json.dumps(subset, default=str)


def _json_sink(message: Any) -> None:
    """Write JSON-serialised log record to stdout."""
    record = message.record
    print(_json_serializer(record), flush=True)


# ---------------------------------------------------------------------------
# Public initialisation
# ---------------------------------------------------------------------------

def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    output_path: str | None = None,
    rotation: str = "100 MB",
    retention: str = "30 days",
    backtrace: bool = True,
    diagnose: bool = False,
) -> None:
    """
    Initialise application logging.

    Call once at application startup (in main.py). Subsequent calls
    are idempotent — Loguru handlers are removed and re-added to avoid
    duplication during tests.

    Args:
        level: Minimum log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        log_format: "json" for structured output, "text" for human-readable.
        output_path: Optional directory path for file-based logging.
        rotation: Loguru rotation trigger, e.g. "100 MB" or "1 day".
        retention: How long to keep rotated files, e.g. "30 days".
        backtrace: Include full stack trace in exceptions.
        diagnose: Include variable values in tracebacks (disable in prod).
    """
    # Remove all existing Loguru handlers
    logger.remove()

    level_upper = level.upper()

    # ── Console sink ────────────────────────────────────────────────────────
    if log_format == "json":
        logger.add(
            _json_sink,
            level=level_upper,
            backtrace=backtrace,
            diagnose=diagnose,
            enqueue=False,
        )
    else:
        text_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        logger.add(
            sys.stdout,
            format=text_format,
            level=level_upper,
            colorize=True,
            backtrace=backtrace,
            diagnose=diagnose,
            enqueue=False,
        )

    # ── File sink (optional) ─────────────────────────────────────────────────
    if output_path:
        log_dir = Path(output_path)
        log_dir.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_dir / "sds_nexus_{time:YYYY-MM-DD}.log",
            level=level_upper,
            rotation=rotation,
            retention=retention,
            compression="gz",
            backtrace=backtrace,
            diagnose=diagnose,
            enqueue=True,   # Thread-safe async writes
            serialize=log_format == "json",
        )

        # Separate error log for rapid triage
        logger.add(
            log_dir / "sds_nexus_errors_{time:YYYY-MM-DD}.log",
            level="ERROR",
            rotation=rotation,
            retention=retention,
            compression="gz",
            backtrace=True,
            diagnose=False,
            enqueue=True,
            serialize=log_format == "json",
        )

    # ── Intercept stdlib logging ─────────────────────────────────────────────
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Silence noisy third-party loggers
    for noisy_logger in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "boto3",
        "botocore",
        "paramiko",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logger.info(
        "Logging initialised",
        level=level_upper,
        format=log_format,
        file_output=output_path or "disabled",
    )


def get_logger(name: str) -> "loguru.Logger":
    """
    Return a Loguru logger bound with the given module name.

    Args:
        name: Typically ``__name__`` from the calling module.

    Returns:
        A Loguru logger with the ``name`` field pre-bound.

    Example::

        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Processing cluster", cluster_id=42)
    """
    return logger.bind(name=name)
