"""Centralized logging configuration."""

from __future__ import annotations

import logging
import sys
from logging.config import dictConfig
from typing import Any, Dict

from app.config import settings


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(funcName)s:%(lineno)d | %(message)s"
)


def configure_logging() -> None:
    """Configure root logging once at application startup."""
    log_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": _LOG_FORMAT,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "format": "%(asctime)s | ACCESS | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "default",
                "level": settings.LOG_LEVEL,
            },
            "access": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "access",
                "level": "INFO",
            },
        },
        "loggers": {
            "": {  # root
                "handlers": ["console"],
                "level": settings.LOG_LEVEL,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": settings.LOG_LEVEL,
                "propagate": False,
            },
        },
    }
    dictConfig(log_config)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for a module."""
    return logging.getLogger(name)


# Configure once on import
configure_logging()
logger = get_logger("app")
