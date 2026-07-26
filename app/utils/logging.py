"""Logging configuration for console and file output."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path, log_level: str = "INFO") -> logging.Logger:
    """Configure root logger with console and rotating file handlers.

    Args:
        log_dir: Directory where log files are written.
        log_level: Logging level name (e.g. INFO, DEBUG).

    Returns:
        Configured root logger instance.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "automation.log"

    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger
