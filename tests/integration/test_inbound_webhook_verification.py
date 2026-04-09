"""
Integration test for inbound webhook signature verification.

Tests the verify_inbound_webhook_signature function in a realistic scenario
with actual webhook payloads and signature generation.

**Validates: Requirements 1.2**
"""
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest

from services.webhook import verify_inbound_webhook_signature


class TestInboundWebhookIntegration:
    """Integration tests for inbound webhook signature verification."""

    def test_realistic_webhook_payload_verification(self):
        """Test signature verification with realistic webhook payload."""
        # Arrange - simulate a real webhook from payment provider
        webhook_secret = "prod-webhook-secret-32-chars-long-abc123"

        payload_dict = {
            "event": "payment.confirmed",
            "tx_ref": "ONEPAY-20240415-ABC123",
            "amount": "15000.00",
            "currency": "NGN",
            "status": "verified",
            "verified_at": "2024-04-15T10:30:00+00:00",
            "customer_email": "customer@example.com",
            "description": "Payment for invoice #12345"
        }

        # Convert to bytes (as it would be in request.data)
        payload_bytes = json.dumps(payload_dict, separators=(',', ':')).encode('utf-8')

        # Generate signature (as payment provider would)
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={computed_sig}"

        # Act - verify signature
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload_bytes, signature_header)

        # Assert
        assert result is True

    def test_tampered_payload_fails_verification(self):
        """Test that tampered payload fails signature verification."""
        # Arrange - original payload
        webhook_secret = "prod-webhook-secret-32-chars-long-abc123"

        original_payload = {
            "tx_ref": "ONEPAY-20240415-ABC123",
            "amount": "15000.00",
            "status": "verified"
        }

        # Generate signature for original payload
        original_bytes = json.dumps(original_payload, separators=(',', ':')).encode('utf-8')
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            original_bytes,
            hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={computed_sig}"

        # Tamper with payload (attacker changes amount)
        tampered_payload = {
            "tx_ref": "ONEPAY-20240415-ABC123",
            "amount": "1.00",  # Changed from 15000.00
            "status": "verified"
        }
        tampered_bytes = json.dumps(tampered_payload, separators=(',', ':')).encode('utf-8')

        # Act - verify tampered payload with original signature
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(tampered_bytes, signature_header)

        # Assert - verification should fail
        assert result is False

    def test_replay_attack_with_different_secret_fails(self):
        """Test that replay attack with different secret fails."""
        # Arrange - attacker captures webhook from different merchant
        merchant1_secret = "merchant1-secret-32-chars-long-abc123"
        merchant2_secret = "merchant2-secret-32-chars-long-xyz789"

        payload = {
            "tx_ref": "ONEPAY-20240415-ABC123",
            "amount": "15000.00",
            "status": "verified"
        }
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        # Generate signature with merchant1's secret
        computed_sig = hmac.new(
            merchant1_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={computed_sig}"

        # Act - try to verify with merchant2's secret (replay attack)
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', merchant2_secret):
            result = verify_inbound_webhook_signature(payload_bytes, signature_header)

        # Assert - verification should fail
        assert result is False

    def test_multiple_webhooks_with_same_secret(self):
        """Test that multiple webhooks can be verified with same secret."""
        # Arrange
        webhook_secret = "prod-webhook-secret-32-chars-long-abc123"

        webhooks = [
            {"tx_ref": "ONEPAY-001", "amount": "1000.00", "status": "verified"},
            {"tx_ref": "ONEPAY-002", "amount": "2000.00", "status": "verified"},
            {"tx_ref": "ONEPAY-003", "amount": "3000.00", "status": "verified"},
        ]

        # Act & Assert - verify each webhook
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            for webhook in webhooks:
                payload_bytes = json.dumps(webhook, separators=(',', ':')).encode('utf-8')
                computed_sig = hmac.new(
                    webhook_secret.encode('utf-8'),
                    payload_bytes,
                    hashlib.sha256
                ).hexdigest()
                signature_header = f"sha256={computed_sig}"

                result = verify_inbound_webhook_signature(payload_bytes, signature_header)
                assert result is True, f"Failed to verify webhook: {webhook['tx_ref']}"

    def test_unicode_characters_in_payload(self):
        """Test signature verification with unicode characters in payload."""
        # Arrange
        webhook_secret = "prod-webhook-secret-32-chars-long-abc123"

        payload = {
            "tx_ref": "ONEPAY-20240415-ABC123",
            "description": "Payment for café ☕ and naïve résumé",
            "customer_name": "José García",
            "amount": "15000.00"
        }

        payload_bytes = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

        # Generate signature
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={computed_sig}"

        # Act
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload_bytes, signature_header)

        # Assert
        assert result is True

    def test_large_payload_verification(self):
        """Test signature verification with large payload."""
        # Arrange
        webhook_secret = "prod-webhook-secret-32-chars-long-abc123"

        # Create large payload with many fields
        payload = {
            "tx_ref": "ONEPAY-20240415-ABC123",
            "amount": "15000.00",
            "status": "verified",
            "metadata": {
                f"field_{i}": f"value_{i}" for i in range(100)
            },
            "items": [
                {"id": i, "name": f"Item {i}", "price": f"{i * 100}.00"}
                for i in range(50)
            ]
        }

        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        # Generate signature
        computed_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={computed_sig}"

        # Act
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', webhook_secret):
            result = verify_inbound_webhook_signature(payload_bytes, signature_header)

        # Assert
        assert result is True
