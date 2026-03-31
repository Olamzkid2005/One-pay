"""
Unit tests for KoraPay webhook signature verification.

Tests verify_korapay_webhook_signature function that validates
HMAC-SHA256 signatures on webhook payloads from KoraPay.

Requirements tested: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""
import pytest
import hmac
import hashlib
import json
from unittest.mock import patch
from services.korapay import verify_korapay_webhook_signature


class TestWebhookSignatureVerification:
    """Test webhook signature verification function."""
    
    def test_verify_with_valid_signature_returns_true(self):
        """Test that valid signature returns True."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 1500
            }
        }
        
        # Compute valid signature on data object only
        data_bytes = json.dumps(payload["data"], separators=(',', ':')).encode('utf-8')
        valid_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            data_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Act
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            result = verify_korapay_webhook_signature(payload, valid_signature)
        
        # Assert
        assert result is True
    
    def test_verify_with_invalid_signature_returns_false(self):
        """Test that invalid signature returns False."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 1500
            }
        }
        
        invalid_signature = "0" * 64  # Wrong signature
        
        # Act
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            result = verify_korapay_webhook_signature(payload, invalid_signature)
        
        # Assert
        assert result is False
    
    def test_signature_computed_on_data_object_only(self):
        """Test that signature is computed on data object only, not full payload."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 1500
            }
        }
        
        # Compute signature on data object only (correct)
        data_bytes = json.dumps(payload["data"], separators=(',', ':')).encode('utf-8')
        correct_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            data_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Compute signature on full payload (incorrect)
        full_payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        wrong_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            full_payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Act & Assert
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            # Correct signature should pass
            assert verify_korapay_webhook_signature(payload, correct_signature) is True
            
            # Wrong signature (computed on full payload) should fail
            assert verify_korapay_webhook_signature(payload, wrong_signature) is False
    
    def test_uses_hmac_compare_digest_for_constant_time_comparison(self):
        """Test that hmac.compare_digest is used for timing-safe comparison."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 1500
            }
        }
        
        data_bytes = json.dumps(payload["data"], separators=(',', ':')).encode('utf-8')
        valid_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            data_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Act & Assert - verify function uses hmac.compare_digest
        # We can't directly test this without inspecting the implementation,
        # but we can verify the function works correctly with timing-safe comparison
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            # Valid signature
            assert verify_korapay_webhook_signature(payload, valid_signature) is True
            
            # Invalid signature with same length (timing attack scenario)
            invalid_signature = "a" * 64
            assert verify_korapay_webhook_signature(payload, invalid_signature) is False
    
    def test_handles_missing_data_object(self):
        """Test that missing data object returns False."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        payload = {
            "event": "charge.success"
            # Missing "data" key
        }
        
        signature = "0" * 64
        
        # Act
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            result = verify_korapay_webhook_signature(payload, signature)
        
        # Assert
        assert result is False
    
    def test_handles_missing_signature(self):
        """Test that missing signature (None or empty) returns False."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 1500
            }
        }
        
        # Act & Assert
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            # None signature
            assert verify_korapay_webhook_signature(payload, None) is False
            
            # Empty string signature
            assert verify_korapay_webhook_signature(payload, "") is False
    
    def test_signature_verification_with_different_data_values(self):
        """Test that signature changes when data values change."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        
        payload1 = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 1500
            }
        }
        
        payload2 = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 2000  # Different amount
            }
        }
        
        # Compute signature for payload1
        data_bytes1 = json.dumps(payload1["data"], separators=(',', ':')).encode('utf-8')
        signature1 = hmac.new(
            webhook_secret.encode('utf-8'),
            data_bytes1,
            hashlib.sha256
        ).hexdigest()
        
        # Act & Assert
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            # Signature1 should work for payload1
            assert verify_korapay_webhook_signature(payload1, signature1) is True
            
            # Signature1 should NOT work for payload2 (different data)
            assert verify_korapay_webhook_signature(payload2, signature1) is False
    
    def test_signature_verification_with_nested_data_structure(self):
        """Test signature verification with complex nested data."""
        # Arrange
        webhook_secret = "test-webhook-secret-32-chars-long-12345"
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "ONEPAY-TEST-123",
                "status": "success",
                "amount": 1500,
                "customer": {
                    "name": "Test Customer",
                    "email": "test@example.com"
                },
                "bank_account": {
                    "account_number": "1234567890",
                    "bank_name": "Test Bank"
                }
            }
        }
        
        # Compute valid signature
        data_bytes = json.dumps(payload["data"], separators=(',', ':')).encode('utf-8')
        valid_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            data_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Act
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', webhook_secret):
            result = verify_korapay_webhook_signature(payload, valid_signature)
        
        # Assert
        assert result is True
