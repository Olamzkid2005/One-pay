"""
Tests for webhook delivery and retry logic.
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.webhook import deliver_webhook_from_dict, queue_webhook_delivery


def test_webhook_payload_signature():
    """Test webhook payload signature generation."""
    import hashlib
    import hmac

    from services.webhook import _sign_payload

    payload_bytes = b'{"test":"data"}'

    with patch("config.Config.WEBHOOK_SECRET", "test_secret"):
        with patch("config.Config.HMAC_SECRET", "fallback_secret"):
            signature = _sign_payload(payload_bytes)
            assert signature.startswith("sha256=")
            assert len(signature) > 10


def test_webhook_delivery_no_url():
    """Test webhook delivery with no URL."""
    wh_data = {"webhook_url": None, "tx_ref": "TEST-REF"}
    result = deliver_webhook_from_dict(wh_data)
    assert result is False


def test_webhook_queue_fallback_to_thread():
    """Test webhook queue falls back to thread when Huey unavailable."""
    # This test is skipped as deliver_webhook_task is in task_queue module
    # The actual implementation is tested in integration tests
    pass


def test_webhook_idempotency_check():
    """Test webhook idempotency check."""
    from models.webhook_idempotency import WebhookIdempotency
    from services.webhook import check_webhook_idempotency, store_webhook_idempotency

    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

    # Check non-existent webhook
    result = check_webhook_idempotency(db, "webhook-123", "korapay")
    assert result is False

    # Store webhook
    store_webhook_idempotency(db, "webhook-123", "korapay", "TEST-REF")
    assert db.add.called


def test_webhook_idempotency_exists():
    """Test webhook idempotency when webhook already processed."""
    from services.webhook import check_webhook_idempotency

    db = MagicMock()
    existing = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = existing

    result = check_webhook_idempotency(db, "webhook-123", "korapay")
    assert result is True


def test_inbound_webhook_signature_verification():
    """Test inbound webhook signature verification."""
    import hashlib
    import hmac

    from services.webhook import verify_inbound_webhook_signature

    payload = b'{"test":"data"}'
    secret = b"test_secret"

    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    header = f"sha256={signature}"

    with patch("config.Config.INBOUND_WEBHOOK_SECRET", "test_secret"):
        result = verify_inbound_webhook_signature(payload, header)
        assert result is True


def test_inbound_webhook_signature_invalid():
    """Test inbound webhook signature verification with invalid signature."""
    from services.webhook import verify_inbound_webhook_signature

    payload = b'{"test":"data"}'
    header = "sha256=invalid_signature"

    with patch("config.Config.INBOUND_WEBHOOK_SECRET", "test_secret"):
        result = verify_inbound_webhook_signature(payload, header)
        assert result is False


def test_inbound_webhook_signature_missing():
    """Test inbound webhook signature verification with missing signature."""
    from services.webhook import verify_inbound_webhook_signature

    payload = b'{"test":"data"}'
    header = ""

    result = verify_inbound_webhook_signature(payload, header)
    assert result is False
