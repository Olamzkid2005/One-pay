#!/usr/bin/env python3
"""
Circuit Breaker Tests for KoraPay Integration

This module tests the CircuitBreaker class functionality.

Requirements: 26.1, 26.2, 26.3
"""

import pytest
import time
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCircuitBreakerBasics:
    """Basic circuit breaker tests."""

    def test_circuit_breaker_starts_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        from services.korapay import CircuitBreaker, CircuitBreakerState

        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_allows_calls_when_closed(self):
        """Test circuit breaker allows calls in CLOSED state."""
        from services.korapay import CircuitBreaker

        cb = CircuitBreaker()

        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"

    def test_circuit_breaker_records_success(self):
        """Test circuit breaker records successes."""
        from services.korapay import CircuitBreaker

        cb = CircuitBreaker()

        for _ in range(5):
            cb.call(lambda: "ok")

        assert cb.state == "closed"

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        from services.korapay import CircuitBreaker, CircuitBreakerState

        cb = CircuitBreaker(failure_threshold=3)

        def fail_func():
            raise Exception("API Error")

        for _ in range(3):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_blocks_calls_when_open(self):
        """Test circuit breaker blocks calls when OPEN."""
        from services.korapay import CircuitBreaker, KoraPayError, CircuitBreakerState

        cb = CircuitBreaker(failure_threshold=1)

        def fail_func():
            raise Exception("API Error")

        with pytest.raises(Exception):
            cb.call(fail_func)

        assert cb.state == CircuitBreakerState.OPEN

        with pytest.raises(KoraPayError) as exc_info:
            cb.call(lambda: "should fail")

        assert exc_info.value.error_code == "CIRCUIT_OPEN"

    def test_circuit_breaker_transitions_to_half_open(self):
        """Test circuit breaker transitions to HALF_OPEN after timeout."""
        from services.korapay import CircuitBreaker, CircuitBreakerState

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        def fail_func():
            raise Exception("API Error")

        with pytest.raises(Exception):
            cb.call(fail_func)

        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(0.15)

        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_closes_after_half_open_successes(self):
        """Test circuit breaker closes after successful half-open calls."""
        from services.korapay import CircuitBreaker, CircuitBreakerState

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)

        def fail_func():
            raise Exception("API Error")

        with pytest.raises(Exception):
            cb.call(fail_func)

        time.sleep(0.15)

        assert cb.state == CircuitBreakerState.HALF_OPEN

        cb.call(lambda: "ok1")
        cb.call(lambda: "ok2")

        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_reopens_on_half_open_failure(self):
        """Test circuit breaker reopens on failure in HALF_OPEN state."""
        from services.korapay import CircuitBreaker, CircuitBreakerState

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        def fail_func():
            raise Exception("API Error")

        with pytest.raises(Exception):
            cb.call(fail_func)

        time.sleep(0.15)

        assert cb.state == CircuitBreakerState.HALF_OPEN

        with pytest.raises(Exception):
            cb.call(fail_func)

        assert cb.state == CircuitBreakerState.OPEN


class TestCircuitBreakerThreadSafety:
    """Thread safety tests for circuit breaker."""

    def test_circuit_breaker_thread_safe(self):
        """Test circuit breaker handles concurrent access."""
        import threading
        from services.korapay import CircuitBreaker, CircuitBreakerState

        cb = CircuitBreaker(failure_threshold=100)

        def safe_func():
            return "ok"

        threads = []
        for _ in range(10):
            t = threading.Thread(target=lambda: cb.call(safe_func))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert cb.state == CircuitBreakerState.CLOSED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])