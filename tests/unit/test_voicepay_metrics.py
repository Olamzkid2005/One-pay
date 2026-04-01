"""
Tests for VoicePay Prometheus metrics.

Tests that VoicePay webhook metrics are properly registered and tracked.
"""
import pytest

# Check if prometheus_client is available
try:
    from prometheus_client import REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="prometheus_client not installed")


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
def test_voicepay_metrics_registered():
    """Test that VoicePay metrics are registered with Prometheus"""
    # Get all registered metric names
    metric_names = [m.name for m in REGISTRY.collect()]
    
    # Verify VoicePay metrics exist
    assert 'voicepay_webhooks_sent_total' in metric_names
    assert 'voicepay_webhook_duration_seconds' in metric_names
    assert 'voicepay_webhook_retries_total' in metric_names
    assert 'voicepay_payment_amount_naira' in metric_names


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
def test_voicepay_webhook_success_metric(monkeypatch):
    """Test that successful webhook delivery increments success counter"""
    from services.voicepay_webhook import send_voicepay_webhook
    from prometheus_client import REGISTRY
    
    # Mock successful response
    class MockResponse:
        status_code = 200
        content = b'{"success": true}'
        
        def json(self):
            return {"success": True}
    
    def mock_post(*args, **kwargs):
        return MockResponse()
    
    monkeypatch.setattr("requests.post", mock_post)
    
    # Get initial metric value
    initial_value = None
    for metric in REGISTRY.collect():
        if metric.name == 'voicepay_webhooks_sent_total':
            for sample in metric.samples:
                if sample.labels.get('status') == 'success':
                    initial_value = sample.value
                    break
    
    # Send webhook
    payload = {"event": "payment.verified", "tx_ref": "VP-TEST-123"}
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/webhook",
        secret="test-secret"
    )
    
    assert result["success"] is True
    
    # Verify metric incremented
    final_value = None
    for metric in REGISTRY.collect():
        if metric.name == 'voicepay_webhooks_sent_total':
            for sample in metric.samples:
                if sample.labels.get('status') == 'success':
                    final_value = sample.value
                    break
    
    if initial_value is not None:
        assert final_value > initial_value


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
def test_voicepay_webhook_failure_metric(monkeypatch):
    """Test that failed webhook delivery increments failure counter"""
    from services.voicepay_webhook import send_voicepay_webhook
    from prometheus_client import REGISTRY
    
    # Mock failed response
    class MockResponse:
        status_code = 500
        content = b'{"error": "Internal server error"}'
        
        def json(self):
            return {"error": "Internal server error"}
    
    def mock_post(*args, **kwargs):
        return MockResponse()
    
    monkeypatch.setattr("requests.post", mock_post)
    
    # Get initial metric value
    initial_value = None
    for metric in REGISTRY.collect():
        if metric.name == 'voicepay_webhooks_sent_total':
            for sample in metric.samples:
                if sample.labels.get('status') == 'failure':
                    initial_value = sample.value
                    break
    
    # Send webhook
    payload = {"event": "payment.verified", "tx_ref": "VP-TEST-456"}
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/webhook",
        secret="test-secret",
        max_retries=1
    )
    
    assert result["success"] is False
    
    # Verify metric incremented
    final_value = None
    for metric in REGISTRY.collect():
        if metric.name == 'voicepay_webhooks_sent_total':
            for sample in metric.samples:
                if sample.labels.get('status') == 'failure':
                    final_value = sample.value
                    break
    
    if initial_value is not None:
        assert final_value > initial_value


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
def test_voicepay_webhook_duration_metric(monkeypatch):
    """Test that webhook duration is tracked"""
    from services.voicepay_webhook import send_voicepay_webhook
    from prometheus_client import REGISTRY
    import time
    
    # Mock response with delay
    class MockResponse:
        status_code = 200
        content = b'{"success": true}'
        
        def json(self):
            return {"success": True}
    
    def mock_post(*args, **kwargs):
        time.sleep(0.1)  # Simulate network delay
        return MockResponse()
    
    monkeypatch.setattr("requests.post", mock_post)
    
    # Send webhook
    payload = {"event": "payment.verified", "tx_ref": "VP-TEST-789"}
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/webhook",
        secret="test-secret"
    )
    
    assert result["success"] is True
    
    # Verify duration metric exists and has samples
    duration_found = False
    for metric in REGISTRY.collect():
        if metric.name == 'voicepay_webhook_duration_seconds':
            duration_found = True
            assert len(metric.samples) > 0
            break
    
    assert duration_found


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
def test_voicepay_payment_amount_metric():
    """Test that payment amounts are tracked"""
    from services.voicepay_webhook import build_voicepay_payload
    from models.transaction import Transaction, TransactionStatus
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from prometheus_client import REGISTRY
    
    # Create transaction
    transaction = Transaction(
        tx_ref="VP-BILL-METRIC-TEST",
        amount=Decimal("15000.00"),
        status=TransactionStatus.VERIFIED,
        customer_email="user@voicepay.ng",
        description="Test payment",
        hash_token="test-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        verified_at=datetime.now(timezone.utc)
    )
    
    # Build payload (should track amount)
    payload = build_voicepay_payload(transaction)
    
    # Verify amount metric exists
    amount_found = False
    for metric in REGISTRY.collect():
        if metric.name == 'voicepay_payment_amount_naira':
            amount_found = True
            break
    
    assert amount_found
