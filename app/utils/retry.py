"""
Retry utilities using the Tenacity library.

Provides pre-configured retry decorators and a context-manager-based
retry helper for use across all service and utility classes that make
network calls (SSH, HTTP, S3, SMTP, etc.).
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    before_sleep_log,
    after_log,
)

from app.core.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Pre-configured retry decorators
# ---------------------------------------------------------------------------

def retry_on_network_error(
    *,
    max_attempts: int = 3,
    wait_min: float = 2.0,
    wait_max: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Retry decorator for transient network errors with exponential back-off.

    Suitable for SSH commands, HTTP requests, and S3 API calls.

    Args:
        max_attempts: Maximum number of total attempts (including the first).
        wait_min: Minimum wait between retries (seconds).
        wait_max: Maximum wait between retries (seconds).
        exceptions: Tuple of exception types that should trigger a retry.

    Returns:
        A decorator that wraps the function with retry logic.

    Example::

        @retry_on_network_error(max_attempts=3)
        def fetch_cluster_status(host: str) -> dict:
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = retry(
                retry=retry_if_exception_type(exceptions),
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
                before_sleep=before_sleep_log(logger, "WARNING"),  # type: ignore[arg-type]
                reraise=True,
            )
            return attempt(func)(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def retry_fixed(
    *,
    max_attempts: int = 3,
    wait_seconds: float = 5.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Retry decorator with a fixed wait interval.

    Suitable for operations where exponential back-off is not appropriate
    (e.g. checking if a resource has become ready).

    Args:
        max_attempts: Maximum total attempts.
        wait_seconds: Fixed wait between retries.
        exceptions: Exception types that trigger retry.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = retry(
                retry=retry_if_exception_type(exceptions),
                stop=stop_after_attempt(max_attempts),
                wait=wait_fixed(wait_seconds),
                reraise=True,
            )
            return attempt(func)(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Utility function
# ---------------------------------------------------------------------------

def execute_with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    wait_seconds: float = 5.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    """
    Execute a callable with retry logic — useful when you cannot modify
    the original function to add a decorator.

    Args:
        func: Callable to execute.
        *args: Positional arguments for the callable.
        max_attempts: Maximum total attempts.
        wait_seconds: Fixed wait between retries (seconds).
        exceptions: Exception types that trigger retry.
        **kwargs: Keyword arguments for the callable.

    Returns:
        Return value of the callable.

    Raises:
        The last exception if all attempts fail.
    """
    last_exc: Exception | None = None
    for attempt_num in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as exc:
            last_exc = exc
            if attempt_num < max_attempts:
                logger.warning(
                    "Retrying after error",
                    attempt=attempt_num,
                    max_attempts=max_attempts,
                    error=str(exc),
                    function=func.__name__,
                )
                import time
                time.sleep(wait_seconds)
            else:
                logger.error(
                    "All retry attempts exhausted",
                    function=func.__name__,
                    max_attempts=max_attempts,
                    error=str(exc),
                )

    raise last_exc  # type: ignore[misc]
