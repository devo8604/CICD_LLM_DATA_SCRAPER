"""Comprehensive exception handling and retry mechanisms for the application."""

import functools
import logging
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from src.core.config import AppConfig

T = TypeVar("T")
P = ParamSpec("P")


# Custom exceptions
class PipelineError(Exception):
    """Base exception for pipeline operations."""

    pass


class LLMError(PipelineError):
    """Exception for LLM-related errors."""

    pass


class FileProcessingError(PipelineError):
    """Exception for file processing errors."""

    pass


class DatabaseError(PipelineError):
    """Exception for database-related errors."""

    pass


class ConfigurationError(PipelineError):
    """Exception for configuration errors."""

    pass


class RetryError(PipelineError):
    """Exception raised when all retry attempts have been exhausted."""

    def __init__(self, original_exception: Exception, attempts: int):
        self.original_exception = original_exception
        self.attempts = attempts
        super().__init__(f"Retry failed after {attempts} attempts. Original error: {str(original_exception)}")


# Decorator for retry logic
def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    config: AppConfig | None = None,
):
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between attempts in seconds
        backoff: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch and retry on
        config: Optional config to override defaults
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            current_delay = delay
            actual_max_attempts = config.LLM_MAX_RETRIES if config else max_attempts

            for attempt in range(actual_max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == actual_max_attempts - 1:  # Last attempt
                        break
                    logging.warning(
                        f"Attempt {attempt + 1} failed with {type(e).__name__}: {e}. "
                        f"Retrying in {current_delay} seconds..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

            raise (
                RetryError(last_exception, actual_max_attempts)
                if last_exception
                else RetryError(Exception("Unknown error"), actual_max_attempts)
            )

        return sync_wrapper

    return decorator


class CircuitBreakerState:
    """Represents the state of a circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit broken
    HALF_OPEN = "half_open"  # Testing if circuit is fixed


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent repeated failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def call(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Call the function with circuit breaker protection."""
        if self._state == CircuitBreakerState.OPEN:
            if time.time() - self._last_failure_time >= self.timeout:
                self._state = CircuitBreakerState.HALF_OPEN
            else:
                raise PipelineError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful operation."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0

    def _on_failure(self):
        """Handle failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN


class TimeoutManager:
    """Manager for handling timeouts with configurable settings."""

    def __init__(self, default_timeout: float = 30.0, config: AppConfig | None = None):
        self.default_timeout = default_timeout
        self.config = config

    @staticmethod
    def run_with_timeout_sync(
        func: Callable[P, T],
        timeout: float,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """
        Run a function with a timeout using threading.

        Args:
            func: The function to run
            timeout: Timeout in seconds
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function

        Raises:
            TimeoutError: If the operation times out
        """
        result = [None]
        exception = [None]
        completed = [False]

        def wrapper():
            try:
                result[0] = func(*args, **kwargs)
                completed[0] = True
            except Exception as e:
                exception[0] = e
                completed[0] = True

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        thread.join(timeout)

        if not completed[0]:
            raise TimeoutError(f"Operation timed out after {timeout} seconds")

        if exception[0]:
            raise exception[0]

        return result[0]


class TimeoutContext:
    """Context manager for timeout operations using threading."""

    def __init__(self, timeout: float | None, error_message: str = "Operation timed out"):
        self.timeout = timeout
        self.error_message = error_message
        self.timer = None
        self.timed_out = False

    def _timeout_handler(self):
        self.timed_out = True

    def __enter__(self):
        if self.timeout:
            self.timer = threading.Timer(self.timeout, self._timeout_handler)
            self.timer.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.timer:
            self.timer.cancel()
        if self.timed_out:
            raise TimeoutError(self.error_message)


def safe_execute(
    func: Callable[P, T],
    *args: P.args,
    default_return: Any = None,
    exception_map: dict[type[Exception], Any] | None = None,
    logger: logging.Logger | None = None,
    **kwargs: P.kwargs,
) -> T:
    """
    Safely execute a function, catching exceptions and returning a default value.

    Args:
        func: Function to execute
        default_return: Value to return if any exception occurs
        exception_map: Map of specific exceptions to specific return values
        logger: Logger to use for logging exceptions
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if exception_map and type(e) in exception_map:
            return exception_map[type(e)]

        if logger:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
        else:
            logging.error(f"Error in {func.__name__}: {e}", exc_info=True)

        return default_return


class GracefulShutdown:
    """Context manager for graceful shutdown of operations."""

    def __init__(self):
        self.shutdown_requested = False

    def request_shutdown(self):
        """Request a graceful shutdown."""
        self.shutdown_requested = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # Cleanup can be added here if needed


# Utility functions for error handling
def format_exception_info(exc: Exception, context: str = "") -> str:
    """Format exception information for logging."""
    return (
        f"Exception in {context or 'unknown context'}: {type(exc).__name__}: {str(exc)}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )


def log_and_raise(logger: logging.Logger, exc: Exception, context: str = ""):
    """Log an exception and re-raise it."""
    logger.error(format_exception_info(exc, context))
    raise exc
