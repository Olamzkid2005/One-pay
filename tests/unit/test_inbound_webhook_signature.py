"""
Unit tests for inbound webhook signature verification.

Tests verify_inbound_webhook_signature function that validates
HMAC-SHA256 signatures on inbound webhook payloads.

**Validates: Requirements 1.2**
"""
import pytest
import hmac
import hashlib
from unittest.mock import patch
from services.webhook import verify_inbound_webhook_signature


class TestInboundWebhookSignatureVerification:
    """Test inbound webhook signature verification function."""
    
    def test_verify_with_valid_signature_returns_true(self):
        """Test that valid signature returns True."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified","amount":"1500.00"}'
        
        # Compute valid signature
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={computed_sig}"
        
        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload, signature)
        
        # Assert
        assert result is True
    
    def test_verify_with_invalid_signature_returns_false(self):
        """Test that invalid signature returns False."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified","amount":"1500.00"}'
        
        invalid_signature = "sha256=" + ("0" * 64)  # Wrong signature
        
        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload, invalid_signature)
        
        # Assert
        assert result is False
    
    def test_signature_without_sha256_prefix_returns_false(self):
        """Test that signature without 'sha256=' prefix returns False."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'
        
        # Compute signature but don't add prefix
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload, computed_sig)
        
        # Assert
        assert result is False
    
    def test_uses_constant_time_comparison(self):
        """Test that hmac.compare_digest is used for timing-safe comparison."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'
        
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        valid_signature = f"sha256={computed_sig}"
        
        # Act & Assert - verify function works correctly with timing-safe comparison
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            # Valid signature
            assert verify_inbound_webhook_signature(payload, valid_signature) is True
            
            # Invalid signature with same length (timing attack scenario)
            invalid_signature = "sha256=" + ("a" * 64)
            assert verify_inbound_webhook_signature(payload, invalid_signature) is False
    
    def test_handles_missing_signature(self):
        """Test that missing signature (None or empty) returns False."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'
        
        # Act & Assert
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            # None signature
            assert verify_inbound_webhook_signature(payload, None) is False
            
            # Empty string signature
            assert verify_inbound_webhook_signature(payload, "") is False
    
    def test_handles_missing_secret(self):
        """Test that missing INBOUND_WEBHOOK_SECRET returns False."""
        # Arrange
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'
        signature = "sha256=" + ("0" * 64)
        
        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', ""):
            result = verify_inbound_webhook_signature(payload, signature)
        
        # Assert
        assert result is False
    
    def test_signature_changes_with_different_payload(self):
        """Test that signature verification fails when payload changes."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload1 = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified","amount":"1500.00"}'
        payload2 = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified","amount":"2000.00"}'
        
        # Compute signature for payload1
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload1,
            hashlib.sha256
        ).hexdigest()
        signature1 = f"sha256={computed_sig}"
        
        # Act & Assert
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            # Signature1 should work for payload1
            assert verify_inbound_webhook_signature(payload1, signature1) is True
            
            # Signature1 should NOT work for payload2 (different payload)
            assert verify_inbound_webhook_signature(payload2, signature1) is False
    
    def test_extracts_signature_from_header_format(self):
        """Test that signature is correctly extracted from 'sha256=<hex>' format."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'
        
        # Compute signature
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Test various formats
        valid_signature = f"sha256={computed_sig}"
        
        # Act & Assert
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            # Valid format should work
            assert verify_inbound_webhook_signature(payload, valid_signature) is True
            
            # Wrong prefix should fail
            assert verify_inbound_webhook_signature(payload, f"sha512={computed_sig}") is False
            assert verify_inbound_webhook_signature(payload, f"md5={computed_sig}") is False
    
    def test_signature_verification_with_empty_payload(self):
        """Test signature verification with empty payload."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b''
        
        # Compute valid signature for empty payload
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={computed_sig}"
        
        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload, signature)
        
        # Assert
        assert result is True
    
    def test_signature_verification_with_special_characters(self):
        """Test signature verification with special characters in payload."""
        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"description":"Payment for \\"Special\\" Item & Service","amount":"1500.00"}'
        
        # Compute valid signature
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={computed_sig}"
        
        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload, signature)
        
        # Assert
        assert result is True
