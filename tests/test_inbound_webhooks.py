"""Tests for inbound webhook receiver"""
import hmac
import hashlib
import json


def test_verify_webhook_signature_valid():
    """Test HMAC signature verification with valid signature"""
    from blueprints.webhooks import verify_webhook_signature
    
    payload = b'{"tx_ref": "TEST123"}'
    secret = "test-secret"
    
    # Generate valid signature
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    # Verify
    assert verify_webhook_signature(payload, f"sha256={sig}", secret) is True


def test_verify_webhook_signature_invalid():
    """Test HMAC signature verification with invalid signature"""
    from blueprints.webhooks import verify_webhook_signature
    
    payload = b'{"tx_ref": "TEST123"}'
    secret = "test-secret"
    
    # Invalid signature
    assert verify_webhook_signature(payload, "sha256=invalid", secret) is False


def test_verify_webhook_signature_wrong_format():
    """Test HMAC signature verification with wrong format"""
    from blueprints.webhooks import verify_webhook_signature
    
    payload = b'{"tx_ref": "TEST123"}'
    secret = "test-secret"
    
    # Missing sha256= prefix
    assert verify_webhook_signature(payload, "abc123", secret) is False
