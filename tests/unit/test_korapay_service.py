"""
Tests for KoraPay service API calls and circuit breaker.
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.korapay import CircuitBreaker, KoraPayError, KoraPayService


def test_korapay_circuit_breaker_initial_state():
    """Test circuit breaker initial state is CLOSED."""
    cb = CircuitBreaker()
    assert cb.state == "closed"
    assert cb.is_available() is True


def test_korapay_circuit_breaker_opens_on_failures():
    """Test circuit breaker opens after threshold failures."""
    from services.korapay import CircuitBreakerState
    cb = CircuitBreaker(failure_threshold=3)

    for _ in range(3):
        cb.record_failure()

    assert cb.state == CircuitBreakerState.OPEN
    assert cb.is_available() is False


def test_korapay_circuit_breaker_recovers():
    """Test circuit breaker recovers to half_open after timeout."""
    import time

    from services.korapay import CircuitBreakerState
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)

    for _ in range(3):
        cb.record_failure()

    assert cb.state == CircuitBreakerState.OPEN

    # Wait for recovery timeout
    time.sleep(0.15)

    # Should transition to half_open
    assert cb.state == CircuitBreakerState.HALF_OPEN


def test_korapay_circuit_breaker_closes_on_success():
    """Test circuit breaker closes after successful calls in half_open."""
    import time

    from services.korapay import CircuitBreakerState
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1, half_open_max_calls=2)

    for _ in range(3):
        cb.record_failure()

    time.sleep(0.15)
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Record successful calls
    for _ in range(2):
        cb.record_success()

    assert cb.state == CircuitBreakerState.CLOSED


def test_korapay_service_mock_mode():
    """Test KoraPay service in mock mode."""
    service = KoraPayService()

    # Should be in mock mode if not configured
    assert service._is_mock() is True


def test_korapay_mock_create_virtual_account():
    """Test mock virtual account creation."""
    service = KoraPayService()

    result = service.create_virtual_account(
        transaction_reference="TEST-REF-123",
        amount_kobo=100000,
        account_name="Test Account"
    )

    assert result["responseCode"] == "Z0"  # pending
    assert "accountNumber" in result
    assert "bankName" in result


def test_korapay_mock_confirm_transfer():
    """Test mock transfer confirmation."""
    service = KoraPayService()

    # First few polls should return pending
    for _ in range(3):
        result = service.confirm_transfer("TEST-REF-123")
        assert result["responseCode"] == "Z0"

    # Fourth poll should return confirmed
    result = service.confirm_transfer("TEST-REF-123")
    assert result["responseCode"] == "00"


def test_korapay_health_metrics():
    """Test health metrics tracking."""
    service = KoraPayService()

    metrics = service.get_health_metrics()
    assert "success_rate" in metrics
    assert "avg_response_time" in metrics
    assert "total_requests" in metrics
    assert "successful_requests" in metrics
    assert "failed_requests" in metrics


def test_korapay_webhook_signature_verification():
    """Test webhook signature verification."""
    import hashlib
    import hmac
    import json

    from services.korapay import verify_korapay_webhook_signature

    # Create test payload and signature
    payload = {"data": {"reference": "TEST-REF", "status": "success"}}
    secret = b"test_secret_key_32_characters_long"

    data_bytes = json.dumps(payload["data"], separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret, data_bytes, hashlib.sha256).hexdigest()

    with patch("config.Config.KORAPAY_WEBHOOK_SECRET", "test_secret_key_32_characters_long"):
        result = verify_korapay_webhook_signature(payload, signature)
        assert result is True


def test_korapay_webhook_signature_invalid():
    """Test webhook signature verification with invalid signature."""
    from services.korapay import verify_korapay_webhook_signature

    payload = {"data": {"reference": "TEST-REF"}}

    with patch("config.Config.KORAPAY_WEBHOOK_SECRET", "test_secret_key_32_characters_long"):
        result = verify_korapay_webhook_signature(payload, "invalid_signature")
        assert result is False
