"""
Tests for VoicePay webhook service.

Tests signature generation, payload building, and webhook delivery
for VoicePay payment confirmation notifications.
"""
import pytest
import json
import hmac
import hashlib
from decimal import Decimal
from datetime import datetime


def test_generate_voicepay_signature():
    """Test HMAC-SHA256 signature generation for VoicePay webhooks"""
    from services.voicepay_webhook import generate_voicepay_signature
    
    payload = {
        "event": "payment.verified",
        "tx_ref": "VP-BILL-123-1234567890",
        "amount": 9000.00
    }
    secret = "test-secret-key-32-characters-long"
    
    signature = generate_voicepay_signature(payload, secret)
    
    # Verify signature format (64 hex characters)
    assert len(signature) == 64
    assert all(c in '0123456789abcdef' for c in signature)
    
    # Verify signature is correct
    message = json.dumps(payload, sort_keys=True)
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    assert signature == expected


def test_generate_voicepay_signature_deterministic():
    """Test that signature generation is deterministic"""
    from services.voicepay_webhook import generate_voicepay_signature
    
    payload = {"event": "payment.verified", "tx_ref": "TEST-123"}
    secret = "test-secret"
    
    sig1 = generate_voicepay_signature(payload, secret)
    sig2 = generate_voicepay_signature(payload, secret)
    
    assert sig1 == sig2


def test_generate_voicepay_signature_different_payloads():
    """Test that different payloads produce different signatures"""
    from services.voicepay_webhook import generate_voicepay_signature
    
    secret = "test-secret"
    
    sig1 = generate_voicepay_signature({"tx_ref": "TEST-1"}, secret)
    sig2 = generate_voicepay_signature({"tx_ref": "TEST-2"}, secret)
    
    assert sig1 != sig2


def test_generate_voicepay_signature_key_order_independent():
    """Test that signature is same regardless of key order in dict"""
    from services.voicepay_webhook import generate_voicepay_signature
    
    secret = "test-secret"
    
    payload1 = {"a": 1, "b": 2, "c": 3}
    payload2 = {"c": 3, "a": 1, "b": 2}
    payload3 = {"b": 2, "c": 3, "a": 1}
    
    sig1 = generate_voicepay_signature(payload1, secret)
    sig2 = generate_voicepay_signature(payload2, secret)
    sig3 = generate_voicepay_signature(payload3, secret)
    
    assert sig1 == sig2 == sig3


def test_generate_voicepay_signature_with_unicode():
    """Test signature generation with Unicode characters"""
    from services.voicepay_webhook import generate_voicepay_signature
    
    payload = {
        "customer_name": "José García",
        "description": "Paiement pour électricité",
        "tx_ref": "VP-BILL-456"
    }
    secret = "test-secret-key"
    
    sig = generate_voicepay_signature(payload, secret)
    assert len(sig) == 64


def test_generate_voicepay_signature_with_nested_objects():
    """Test signature generation with nested metadata"""
    from services.voicepay_webhook import generate_voicepay_signature
    
    payload = {
        "tx_ref": "VP-BILL-789",
        "metadata": {
            "user": {
                "id": "123",
                "name": "John Doe"
            },
            "bill": {
                "type": "dstv",
                "package": "premium"
            }
        }
    }
    secret = "test-secret-key"
    
    sig = generate_voicepay_signature(payload, secret)
    assert len(sig) == 64



def test_build_voicepay_payload():
    """Test building VoicePay webhook payload from transaction"""
    from services.voicepay_webhook import build_voicepay_payload
    from models.transaction import Transaction
    
    # Create mock transaction
    transaction = Transaction(
        tx_ref="VP-BILL-123-1234567890",
        amount=Decimal("9000.00"),
        status="VERIFIED",
        customer_email="user@voicepay.ng",
        description="DSTV Premium Subscription",
        metadata={
            "source": "voicepay",
            "user_id": "123",
            "bill_type": "dstv"
        }
    )
    transaction.paid_at = datetime(2026, 4, 1, 10, 30, 0)
    
    payload = build_voicepay_payload(transaction)
    
    # Verify payload structure
    assert payload["event"] == "payment.verified"
    assert payload["tx_ref"] == "VP-BILL-123-1234567890"
    assert payload["amount"] == 9000.00
    assert payload["currency"] == "NGN"
    assert payload["status"] == "VERIFIED"
    assert payload["customer_email"] == "user@voicepay.ng"
    assert payload["description"] == "DSTV Premium Subscription"
    assert payload["metadata"]["source"] == "voicepay"
    assert payload["metadata"]["user_id"] == "123"
    assert "paid_at" in payload


def test_build_voicepay_payload_with_null_paid_at():
    """Test building payload when paid_at is None"""
    from services.voicepay_webhook import build_voicepay_payload
    from models.transaction import Transaction
    
    transaction = Transaction(
        tx_ref="VP-BILL-456",
        amount=Decimal("5000.00"),
        status="PENDING",
        customer_email="user@voicepay.ng",
        description="Test payment",
        metadata={"source": "voicepay"}
    )
    transaction.paid_at = None
    
    payload = build_voicepay_payload(transaction)
    
    assert payload["paid_at"] is None
    assert payload["status"] == "PENDING"


def test_build_voicepay_payload_with_empty_metadata():
    """Test building payload when metadata is None or empty"""
    from services.voicepay_webhook import build_voicepay_payload
    from models.transaction import Transaction
    
    transaction = Transaction(
        tx_ref="VP-BILL-789",
        amount=Decimal("1000.00"),
        status="VERIFIED",
        customer_email="user@voicepay.ng",
        description="Test payment",
        metadata=None
    )
    transaction.paid_at = datetime(2026, 4, 1, 12, 0, 0)
    
    payload = build_voicepay_payload(transaction)
    
    assert payload["metadata"] == {}
    assert payload["event"] == "payment.verified"


def test_build_voicepay_payload_decimal_to_float_conversion():
    """Test that Decimal amounts are converted to float"""
    from services.voicepay_webhook import build_voicepay_payload
    from models.transaction import Transaction
    
    transaction = Transaction(
        tx_ref="VP-BILL-999",
        amount=Decimal("12345.67"),
        status="VERIFIED",
        customer_email="user@voicepay.ng",
        description="Test payment",
        metadata={"source": "voicepay"}
    )
    transaction.paid_at = datetime(2026, 4, 1, 12, 0, 0)
    
    payload = build_voicepay_payload(transaction)
    
    assert isinstance(payload["amount"], float)
    assert payload["amount"] == 12345.67



# Webhook delivery tests using monkeypatch
def test_send_voicepay_webhook_success(monkeypatch):
    """Test successful webhook delivery to VoicePay"""
    from services.voicepay_webhook import send_voicepay_webhook
    
    # Mock successful response
    class MockResponse:
        status_code = 200
        content = b'{"success": true, "tx_ref": "VP-123"}'
        
        def json(self):
            return {"success": True, "tx_ref": "VP-123"}
    
    def mock_post(*args, **kwargs):
        return MockResponse()
    
    monkeypatch.setattr("requests.post", mock_post)
    
    payload = {
        "event": "payment.verified",
        "tx_ref": "VP-123",
        "amount": 9000.00
    }
    
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/api/webhooks/onepay",
        secret="test-secret"
    )
    
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["tx_ref"] == "VP-123"


def test_send_voicepay_webhook_failure(monkeypatch):
    """Test webhook delivery failure handling"""
    from services.voicepay_webhook import send_voicepay_webhook
    
    # Mock error response
    class MockResponse:
        status_code = 500
        content = b'{"error": "Internal server error"}'
        
        def json(self):
            return {"error": "Internal server error"}
    
    def mock_post(*args, **kwargs):
        return MockResponse()
    
    monkeypatch.setattr("requests.post", mock_post)
    
    payload = {"event": "payment.verified", "tx_ref": "VP-123"}
    
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/api/webhooks/onepay",
        secret="test-secret",
        max_retries=1  # Reduce retries for faster test
    )
    
    assert result["success"] is False
    assert result["status_code"] == 500


def test_send_voicepay_webhook_includes_signature(monkeypatch):
    """Test that webhook includes HMAC signature in header"""
    from services.voicepay_webhook import send_voicepay_webhook, generate_voicepay_signature
    
    captured_headers = {}
    
    class MockResponse:
        status_code = 200
        content = b'{"success": true}'
        
        def json(self):
            return {"success": True}
    
    def mock_post(*args, **kwargs):
        captured_headers.update(kwargs.get('headers', {}))
        return MockResponse()
    
    monkeypatch.setattr("requests.post", mock_post)
    
    payload = {"event": "payment.verified", "tx_ref": "VP-123"}
    secret = "test-secret"
    
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/api/webhooks/onepay",
        secret=secret
    )
    
    # Verify signature header was included
    assert "X-OnePay-Signature" in captured_headers
    
    # Verify signature is correct
    expected_sig = generate_voicepay_signature(payload, secret)
    assert captured_headers["X-OnePay-Signature"] == expected_sig


def test_send_voicepay_webhook_timeout(monkeypatch):
    """Test webhook timeout handling"""
    from services.voicepay_webhook import send_voicepay_webhook
    import requests
    
    def mock_post(*args, **kwargs):
        raise requests.Timeout("Request timed out")
    
    monkeypatch.setattr("requests.post", mock_post)
    
    payload = {"event": "payment.verified", "tx_ref": "VP-123"}
    
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/api/webhooks/onepay",
        secret="test-secret",
        timeout=1,
        max_retries=1
    )
    
    assert result["success"] is False
    assert "error" in result


def test_send_voicepay_webhook_connection_error(monkeypatch):
    """Test webhook connection error handling"""
    from services.voicepay_webhook import send_voicepay_webhook
    import requests
    
    def mock_post(*args, **kwargs):
        raise requests.ConnectionError("Connection failed")
    
    monkeypatch.setattr("requests.post", mock_post)
    
    payload = {"event": "payment.verified", "tx_ref": "VP-123"}
    
    result = send_voicepay_webhook(
        payload=payload,
        webhook_url="https://voicepay.ng/api/webhooks/onepay",
        secret="test-secret",
        max_retries=1
    )
    
    assert result["success"] is False
    assert "error" in result
