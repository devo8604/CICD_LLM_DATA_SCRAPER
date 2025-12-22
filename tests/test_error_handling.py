import time
from unittest.mock import MagicMock

import pytest

from src.core.error_handling import (
    AppConfig,
    CircuitBreaker,
    CircuitBreakerState,
    GracefulShutdown,
    PipelineError,
    RetryError,
    TimeoutContext,
    TimeoutManager,
    log_and_raise,
    retry,
    safe_execute,
)


class TestErrorHandling:
    def test_retry_success(self):
        mock_func = MagicMock(return_value="success")

        @retry(max_attempts=3)
        def decorated_func():
            return mock_func()

        assert decorated_func() == "success"
        assert mock_func.call_count == 1

    def test_retry_failure_recovery(self):
        mock_func = MagicMock(side_effect=[ValueError("Fail"), "success"])

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def decorated_func():
            return mock_func()

        assert decorated_func() == "success"
        assert mock_func.call_count == 2

    def test_retry_exhausted(self):
        mock_func = MagicMock(side_effect=ValueError("Fail"))

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def decorated_func():
            return mock_func()

        with pytest.raises(RetryError) as exc:
            decorated_func()

        assert exc.value.attempts == 3
        assert isinstance(exc.value.original_exception, ValueError)
        assert mock_func.call_count == 3

    def test_retry_with_config(self):
        config = MagicMock(spec=AppConfig)
        config.LLM_MAX_RETRIES = 2

        mock_func = MagicMock(side_effect=ValueError("Fail"))

        @retry(config=config, delay=0.01, exceptions=(ValueError,))
        def decorated_func():
            return mock_func()

        with pytest.raises(RetryError):
            decorated_func()

        assert mock_func.call_count == 2

    def test_circuit_breaker_normal(self):
        cb = CircuitBreaker(failure_threshold=2)
        mock_func = MagicMock(return_value="success")

        assert cb.call(mock_func) == "success"
        assert cb._state == CircuitBreakerState.CLOSED
        assert cb._failure_count == 0

    def test_circuit_breaker_open(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        mock_func = MagicMock(side_effect=Exception("Fail"))

        # 1st failure
        with pytest.raises(Exception):
            cb.call(mock_func)
        assert cb._state == CircuitBreakerState.CLOSED
        assert cb._failure_count == 1

        # 2nd failure - opens circuit
        with pytest.raises(Exception):
            cb.call(mock_func)
        assert cb._state == CircuitBreakerState.OPEN

        # Circuit open - calls blocked
        with pytest.raises(PipelineError, match="Circuit breaker is OPEN"):
            cb.call(mock_func)

    def test_circuit_breaker_half_open_recovery(self):
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        mock_func = MagicMock(side_effect=Exception("Fail"))

        # Fail to open
        with pytest.raises(Exception):
            cb.call(mock_func)
        assert cb._state == CircuitBreakerState.OPEN

        # Wait for timeout
        time.sleep(0.2)

        # Next call should be allowed (half-open)
        mock_func.side_effect = None
        mock_func.return_value = "success"

        assert cb.call(mock_func) == "success"
        assert cb._state == CircuitBreakerState.CLOSED
        assert cb._failure_count == 0

    def test_timeout_manager_sync_success(self):
        def task():
            return "done"

        result = TimeoutManager.run_with_timeout_sync(task, 1.0)
        assert result == "done"

    def test_timeout_manager_sync_timeout(self):
        def task():
            time.sleep(0.2)

        with pytest.raises(TimeoutError):
            TimeoutManager.run_with_timeout_sync(task, 0.1)

    def test_timeout_manager_sync_exception(self):
        def task():
            raise ValueError("Error")

        with pytest.raises(ValueError):
            TimeoutManager.run_with_timeout_sync(task, 1.0)

    def test_timeout_context_success(self):
        with TimeoutContext(1.0):
            pass

    def test_timeout_context_timeout(self):
        # Note: TimeoutContext using threading.Timer raises exception in the timer thread?
        # No, it sets self.timed_out = True and raises in __exit__?
        # Wait, the implementation of TimeoutContext:
        # def _timeout_handler(self): self.timed_out = True
        # def __exit__(self, ...): if self.timed_out: raise TimeoutError

        # But this doesn't interrupt the code block! It only checks at exit.
        # This is a passive timeout check.

        with pytest.raises(TimeoutError):
            with TimeoutContext(0.1):
                time.sleep(0.2)

    def test_safe_execute_success(self):
        assert safe_execute(lambda: "success") == "success"

    def test_safe_execute_exception_default(self):
        assert safe_execute(lambda: 1 / 0, default_return="failed") == "failed"

    def test_safe_execute_exception_map(self):
        exception_map = {ZeroDivisionError: "infinity"}
        assert safe_execute(lambda: 1 / 0, exception_map=exception_map) == "infinity"

    def test_safe_execute_logging(self):
        logger = MagicMock()
        safe_execute(lambda: 1 / 0, logger=logger)
        logger.error.assert_called()

    def test_graceful_shutdown(self):
        with GracefulShutdown() as gs:
            assert gs.shutdown_requested is False
            gs.request_shutdown()
            assert gs.shutdown_requested is True

    def test_log_and_raise(self):
        logger = MagicMock()
        with pytest.raises(ValueError):
            log_and_raise(logger, ValueError("Error"), "context")
        logger.error.assert_called()
