"""Retry helpers for transient automation failures."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from playwright.async_api import Error as PlaywrightError
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.settings import Settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

RETRYABLE_EXCEPTIONS = (
    PlaywrightError,
    ConnectionError,
    OSError,
)


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts with exception context."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retry attempt %s after error: %s",
        retry_state.attempt_number,
        exc,
    )


def with_retries(settings: Settings) -> Callable[[F], F]:
    """Return a retry decorator configured from application settings."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_min_wait_seconds,
            max=settings.retry_max_wait_seconds,
        ),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=_log_retry,
    )
