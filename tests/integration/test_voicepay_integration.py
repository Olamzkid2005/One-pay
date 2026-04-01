"""
Integration tests for VoicePay webhook forwarding.

Tests the complete flow from KoraPay webhook receipt to VoicePay webhook delivery.
"""
import pytest
import json
import hmac
import hashlib
from decimal import Decimal
from datetime import datetime
from app import create_app
from database import get_db
from models.transaction import Transaction


@pytest.fixture
def app():
    """Create test app"""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


def test_korapay_webhook_forwards_to_voicepay(client, monkeypatch):
    """Test that KoraPay webhook triggers VoicePay webhook"""
    from config import Config
    from datetime import datetime, timezone, timedelta
    from services.security import generate_hash_token
    
    # Track VoicePay webhook calls
    voicepay_calls = []
    
    def mock_send_voicepay_webhook(payload, webhook_url, secret, **kwargs):
        voicepay_calls.append({
            "payload": payload,
            "webhook_url": webhook_url,
            "secret": secret
        })
        return {"success": True, "status_code": 200, "tx_ref": payload["tx_ref"]}
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_voicepay_webhook
    )
    
    # Enable VoicePay integration
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/api/webhooks/onepay')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'test-voicepay-secret')
    
    # Create test transaction with VoicePay tx_ref prefix
    tx_ref = "VP-BILL-123-1234567890"
    amount = Decimal("9000.00")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    hash_token = generate_hash_token(tx_ref, amount, expires_at)
    
    with get_db() as db:
        transaction = Transaction(
            tx_ref=tx_ref,
            amount=amount,
            status="PENDING",
            customer_email="user@voicepay.ng",
            description="DSTV Premium",
            user_id=1,
            hash_token=hash_token,
            expires_at=expires_at
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "VP-BILL-123-1234567890",
            "status": "success",
            "amount": 9000
        }
    }
    
    # Generate KoraPay signature
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    korapay_signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Send webhook
    response = client.post(
        "/api/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": korapay_signature}
    )
    
    assert response.status_code == 200
    
    # Verify VoicePay webhook was called
    assert len(voicepay_calls) == 1
    assert voicepay_calls[0]["payload"]["tx_ref"] == "VP-BILL-123-1234567890"
    assert voicepay_calls[0]["payload"]["event"] == "payment.verified"
    assert voicepay_calls[0]["payload"]["status"] == "VERIFIED"
    assert voicepay_calls[0]["payload"]["amount"] == 9000.00


def test_non_voicepay_transaction_no_webhook(client, monkeypatch):
    """Test that non-VoicePay transactions don't trigger VoicePay webhook"""
    from config import Config
    from datetime import datetime, timezone, timedelta
    from services.security import generate_hash_token
    
    webhook_calls = []
    
    def mock_send_voicepay_webhook(payload, webhook_url, secret, **kwargs):
        webhook_calls.append(payload)
        return {"success": True, "status_code": 200, "tx_ref": payload["tx_ref"]}
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_voicepay_webhook
    )
    
    # Enable VoicePay integration
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Create regular OnePay transaction (no VoicePay prefix)
    tx_ref = "ONEPAY-REGULAR-123"
    amount = Decimal("5000.00")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    hash_token = generate_hash_token(tx_ref, amount, expires_at)
    
    with get_db() as db:
        transaction = Transaction(
            tx_ref=tx_ref,
            amount=amount,
            status="PENDING",
            customer_email="user@example.com",
            description="Regular payment",
            user_id=1,
            hash_token=hash_token,
            expires_at=expires_at
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "ONEPAY-REGULAR-123",
            "status": "success",
            "amount": 5000
        }
    }
    
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    korapay_signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": korapay_signature}
    )
    
    assert response.status_code == 200
    
    # Verify VoicePay webhook was NOT called
    assert len(webhook_calls) == 0


def test_voicepay_webhook_disabled_no_forwarding(client, monkeypatch):
    """Test that webhooks are not forwarded when VoicePay is disabled"""
    from config import Config
    from datetime import datetime, timezone, timedelta
    from services.security import generate_hash_token
    
    webhook_calls = []
    
    def mock_send_voicepay_webhook(payload, webhook_url, secret, **kwargs):
        webhook_calls.append(payload)
        return {"success": True, "status_code": 200, "tx_ref": payload["tx_ref"]}
    
    monkeypatch.setattr(
        "services.voicepay_webhook.send_voicepay_webhook",
        mock_send_voicepay_webhook
    )
    
    # Disable VoicePay integration
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'false')
    
    # Create VoicePay transaction
    tx_ref = "VP-BILL-DISABLED-123"
    amount = Decimal("9000.00")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    hash_token = generate_hash_token(tx_ref, amount, expires_at)
    
    with get_db() as db:
        transaction = Transaction(
            tx_ref=tx_ref,
            amount=amount,
            status="PENDING",
            customer_email="user@voicepay.ng",
            description="Test payment",
            user_id=1,
            hash_token=hash_token,
            expires_at=expires_at
        )
        db.add(transaction)
        db.flush()
    
    # Simulate KoraPay webhook
    korapay_payload = {
        "event": "charge.success",
        "data": {
            "reference": "VP-BILL-DISABLED-123",
            "status": "success",
            "amount": 9000
        }
    }
    
    data_bytes = json.dumps(korapay_payload["data"], separators=(',', ':')).encode()
    korapay_signature = hmac.new(
        Config.KORAPAY_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/api/webhooks/korapay",
        json=korapay_payload,
        headers={"x-korapay-signature": korapay_signature}
    )
    
    assert response.status_code == 200
    
    # Verify VoicePay webhook was NOT called (disabled)
    assert len(webhook_calls) == 0
