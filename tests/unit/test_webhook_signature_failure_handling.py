"""
Unit tests for webhook signature failure handling.

Tests that the webhook endpoint returns HTTP 401 and logs client IP
when signature verification fails.

Requirements tested: 1.3
"""
import hashlib
import hmac
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask


@pytest.fixture
def app():
    """Create test Flask app with error handlers."""
    import os

    from app import create_app

    # Set test environment
    os.environ['APP_ENV'] = 'testing'
    os.environ['INBOUND_WEBHOOK_SECRET'] = 'test-secret-32-characters-long!'

    app = create_app()
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


class TestWebhookSignatureFailureHandling:
    """Test webhook signature failure handling (Requirement 1.3)."""

    def test_invalid_signature_returns_401(self, client) -> None:
        """
        Test that invalid signature returns HTTP 401.

        Requirement 1.3: WHEN signature verification fails,
        THE Webhook_Handler SHALL return HTTP 401 Unauthorized
        """
        # Mock config
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', 'test-secret'):
            # Prepare webhook payload
            payload = {"tx_ref": "TEST123", "status": "verified"}
            payload_bytes = json.dumps(payload, separators=(',', ':')).encode()

            # Use invalid signature
            invalid_signature = "sha256=invalid_signature_here"

            # Send webhook with invalid signature
            response = client.post(
                '/api/v1/webhooks/payment-status',
                data=payload_bytes,
                content_type='application/json',
                headers={'X-Webhook-Signature': invalid_signature}
            )

            # Verify HTTP 401 response
            assert response.status_code == 401

            # Verify error response format
            data = response.get_json()
            assert data['success'] is False
            assert data['error_code'] == 'AUTHENTICATION_ERROR'
            assert 'signature' in data['message'].lower()

    def test_missing_signature_returns_401(self, client) -> None:
        """
        Test that missing signature returns HTTP 401.

        Requirement 1.3: WHEN signature verification fails,
        THE Webhook_Handler SHALL return HTTP 401 Unauthorized
        """
        # Mock config
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', 'test-secret'):
            # Prepare webhook payload
            payload = {"tx_ref": "TEST123", "status": "verified"}
            payload_bytes = json.dumps(payload, separators=(',', ':')).encode()

            # Send webhook without signature header
            response = client.post(
                '/api/v1/webhooks/payment-status',
                data=payload_bytes,
                content_type='application/json'
            )

            # Verify HTTP 401 response
            assert response.status_code == 401

            # Verify error response format
            data = response.get_json()
            assert data['success'] is False
            assert data['error_code'] == 'AUTHENTICATION_ERROR'

    def test_signature_failure_logs_client_ip(self, client) -> None:
        """
        Test that signature failure logs client IP address.

        Requirement 1.3: WHEN signature verification fails,
        THE Webhook_Handler SHALL log the client IP address
        """
        # Mock config and logger
        with patch('config.Config.INBOUND_WEBHOOK_SECRET', 'test-secret'):
            with patch('blueprints.webhooks.logger') as mock_logger:
                with patch('core.ip.client_ip', return_value='192.168.1.100'):
                    # Prepare webhook payload
                    payload = {"tx_ref": "TEST123", "status": "verified"}
                    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()

                    # Use invalid signature
                    invalid_signature = "sha256=invalid_signature_here"

                    # Send webhook with invalid signature
                    response = client.post(
                        '/api/v1/webhooks/payment-status',
                        data=payload_bytes,
                        content_type='application/json',
                        headers={'X-Webhook-Signature': invalid_signature}
                    )

                    # Verify HTTP 401 response
                    assert response.status_code == 401

                    # Verify logger.warning was called with client IP
                    mock_logger.warning.assert_called_once()
                    log_call_args = mock_logger.warning.call_args

                    # Check that the log message contains the expected format
                    assert 'Invalid webhook signature' in log_call_args[0][0]
                    assert '192.168.1.100' in str(log_call_args)

    def test_valid_signature_does_not_return_401(self, client) -> None:
        """
        Test that valid signature does NOT return HTTP 401.

        This is a positive test to ensure the failure handling
        doesn't affect valid requests.
        """
        # Mock database and config
        with patch('database.get_db') as mock_get_db:
            with patch('config.Config.INBOUND_WEBHOOK_SECRET', 'test-secret'):
                mock_db = MagicMock()

                @contextmanager
                def mock_db_context():
                    try:
                        yield mock_db
                        mock_db.commit()
                    except Exception:
                        mock_db.rollback()
                        raise

                mock_get_db.return_value = mock_db_context()

                # Create mock transaction
                from datetime import datetime, timedelta, timezone

                from models.transaction import Transaction, TransactionStatus

                mock_tx = MagicMock(spec=Transaction)
                mock_tx.tx_ref = "TEST123"
                mock_tx.status = TransactionStatus.PENDING
                mock_tx.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

                mock_db.query.return_value.filter.return_value.first.return_value = mock_tx

                # Prepare webhook payload
                payload = {"tx_ref": "TEST123", "status": "verified"}
                payload_bytes = json.dumps(payload, separators=(',', ':')).encode()

                # Generate valid signature
                secret = 'test-secret'
                sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
                valid_signature = f"sha256={sig}"

                # Send webhook with valid signature
                response = client.post(
                    '/api/v1/webhooks/payment-status',
                    data=payload_bytes,
                    content_type='application/json',
                    headers={'X-Webhook-Signature': valid_signature}
                )

                # Verify NOT 401 (should be 200 for valid signature)
                assert response.status_code == 200

                # Verify success response
                data = response.get_json()
                assert data['success'] is True
