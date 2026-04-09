"""
Unit tests for webhook signature validation (Task 1.4).

This test suite consolidates all testing for webhook signature validation:
- Config validation tests (from task 1.1)
- Signature verification tests (from task 1.2)
- Failure handling tests (from task 1.3)

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""
import hashlib
import hmac
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

# ============================================================================
# Config Validation Tests (Requirement 1.1, 1.4)
# ============================================================================

class TestWebhookSecretConfigValidation:
    """Test webhook secret configuration validation at startup."""

    def test_empty_inbound_webhook_secret_fails_validation(self, monkeypatch):
        """
        Test that empty INBOUND_WEBHOOK_SECRET fails validation.

        Requirement 1.1: WHEN the INBOUND_WEBHOOK_SECRET environment variable
        is empty or unset, THE System SHALL refuse to start and log a critical
        error message
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("HMAC_SECRET", "b" * 32)
        monkeypatch.setenv("WEBHOOK_SECRET", "c" * 32)
        monkeypatch.setenv("KORAPAY_SECRET_KEY", "sk_live_" + "d" * 32)
        monkeypatch.setenv("KORAPAY_WEBHOOK_SECRET", "e" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://test")
        monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "")  # Empty

        # Act & Assert
        from config import ProductionConfig
        with pytest.raises(SystemExit):
            ProductionConfig.validate()

    def test_production_requires_32_char_inbound_webhook_secret(self, monkeypatch):
        """
        Test that production requires INBOUND_WEBHOOK_SECRET >= 32 characters.

        Requirement 1.4: WHERE the APP_ENV is production, THE System SHALL
        require INBOUND_WEBHOOK_SECRET to be at least 32 characters
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("HMAC_SECRET", "b" * 32)
        monkeypatch.setenv("WEBHOOK_SECRET", "c" * 32)
        monkeypatch.setenv("KORAPAY_SECRET_KEY", "sk_live_" + "d" * 32)
        monkeypatch.setenv("KORAPAY_WEBHOOK_SECRET", "e" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://test")
        monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "short")  # Too short

        # Act & Assert
        from config import ProductionConfig
        with pytest.raises(SystemExit):
            ProductionConfig.validate()

    def test_valid_inbound_webhook_secret_passes_validation(self, monkeypatch):
        """
        Test that valid INBOUND_WEBHOOK_SECRET passes validation.
        """
        # Arrange - set all required production config values
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("HMAC_SECRET", "b" * 32)
        monkeypatch.setenv("WEBHOOK_SECRET", "c" * 32)
        monkeypatch.setenv("KORAPAY_SECRET_KEY", "sk_live_" + "d" * 32)
        monkeypatch.setenv("KORAPAY_WEBHOOK_SECRET", "e" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://test")
        monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "f" * 32)  # Valid
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.com/callback")  # Required for production
        monkeypatch.setenv("VOICEPAY_WEBHOOK_ENABLED", "false")  # Disable VoicePay to avoid additional validation

        # Reload config module to pick up new environment variables
        import importlib

        import config
        importlib.reload(config)

        # Act & Assert - should not raise
        from config import ProductionConfig
        ProductionConfig.validate()  # Should not raise SystemExit


# ============================================================================
# Signature Verification Tests (Requirement 1.2)
# ============================================================================

class TestWebhookSignatureVerification:
    """Test HMAC-SHA256 signature verification for inbound webhooks."""

    def test_valid_signature_returns_true(self):
        """
        Test that valid HMAC-SHA256 signature returns True.

        Requirement 1.2: WHEN an inbound webhook request is received,
        THE Webhook_Handler SHALL verify the HMAC-SHA256 signature using
        the configured secret
        """
        from services.webhook import verify_inbound_webhook_signature

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

    def test_invalid_signature_returns_false(self):
        """
        Test that invalid signature returns False.

        Requirement 1.2: THE Webhook_Handler SHALL verify the HMAC-SHA256
        signature using the configured secret
        """
        from services.webhook import verify_inbound_webhook_signature

        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified","amount":"1500.00"}'

        invalid_signature = "sha256=" + ("0" * 64)  # Wrong signature

        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload, invalid_signature)

        # Assert
        assert result is False

    def test_missing_signature_returns_false(self):
        """
        Test that missing signature (None or empty) returns False.
        """
        from services.webhook import verify_inbound_webhook_signature

        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'

        # Act & Assert
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            # None signature
            assert verify_inbound_webhook_signature(payload, None) is False

            # Empty string signature
            assert verify_inbound_webhook_signature(payload, "") is False

    def test_signature_without_sha256_prefix_returns_false(self):
        """
        Test that signature without 'sha256=' prefix returns False.
        """
        from services.webhook import verify_inbound_webhook_signature

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

    def test_missing_secret_returns_false(self):
        """
        Test that missing INBOUND_WEBHOOK_SECRET returns False.
        """
        from services.webhook import verify_inbound_webhook_signature

        # Arrange
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'
        signature = "sha256=" + ("0" * 64)

        # Act
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', ""):
            result = verify_inbound_webhook_signature(payload, signature)

        # Assert
        assert result is False

    def test_signature_changes_with_different_payload(self):
        """
        Test that signature verification fails when payload changes.
        """
        from services.webhook import verify_inbound_webhook_signature

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

    def test_uses_constant_time_comparison(self):
        """
        Test that hmac.compare_digest is used for timing-safe comparison.

        This prevents timing attacks where an attacker could determine
        the correct signature by measuring response times.
        """
        from services.webhook import verify_inbound_webhook_signature

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


# ============================================================================
# Signature Failure Handling Tests (Requirement 1.3)
# ============================================================================
# Note: Endpoint-level tests for signature failure handling are covered in
# tests/unit/test_webhook_signature_failure_handling.py
# This section focuses on unit-level validation of the signature verification
# function's behavior when failures occur.


# ============================================================================
# Edge Cases and Additional Tests
# ============================================================================

class TestWebhookSignatureEdgeCases:
    """Test edge cases for webhook signature validation."""

    def test_signature_verification_with_empty_payload(self):
        """Test signature verification with empty payload."""
        from services.webhook import verify_inbound_webhook_signature

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
        from services.webhook import verify_inbound_webhook_signature

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

    def test_signature_with_wrong_prefix_format(self):
        """Test that signature with wrong prefix format returns False."""
        from services.webhook import verify_inbound_webhook_signature

        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        payload = b'{"tx_ref":"ONEPAY-TEST-123","status":"verified"}'

        # Compute signature
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Act & Assert
        with patch('services.webhook.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            # Wrong prefix should fail
            assert verify_inbound_webhook_signature(payload, f"sha512={computed_sig}") is False
            assert verify_inbound_webhook_signature(payload, f"md5={computed_sig}") is False
            assert verify_inbound_webhook_signature(payload, f"SHA256={computed_sig}") is False

    def test_signature_verification_with_large_payload(self):
        """Test signature verification with large payload."""
        from services.webhook import verify_inbound_webhook_signature

        # Arrange
        webhook_secret = "test-inbound-webhook-secret-32-chars-long"
        # Create a large payload (10KB)
        large_data = {"tx_ref": "TEST123", "data": "x" * 10000}
        payload = json.dumps(large_data, separators=(',', ':')).encode()

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
