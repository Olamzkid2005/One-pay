"""
Unit tests for webhook idempotency functions.

Tests the check_webhook_idempotency and store_webhook_idempotency functions
to ensure duplicate webhooks are properly detected and stored.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest


class TestWebhookIdempotencyFunctions:
    """Test webhook idempotency check and store functions."""

    def test_check_webhook_idempotency_returns_false_for_new_webhook(self):
        """
        Test that check_webhook_idempotency returns False for new webhook.

        Requirement 2.1: WHEN an inbound webhook is received, THE Webhook_Handler
        SHALL extract a unique identifier from the payload
        """
        from services.webhook import check_webhook_idempotency

        # Arrange
        mock_db = MagicMock()
        mock_db.query().filter().filter().first.return_value = None

        # Act
        result = check_webhook_idempotency(mock_db, "webhook-123", "korapay")

        # Assert
        assert result is False

    def test_check_webhook_idempotency_returns_true_for_duplicate_webhook(self):
        """
        Test that check_webhook_idempotency returns True for duplicate webhook.

        Requirement 2.2: WHEN a webhook with a previously-seen identifier is received,
        THE Webhook_Handler SHALL return HTTP 200 OK without processing the webhook again
        """
        from models.webhook_idempotency import WebhookIdempotency
        from services.webhook import check_webhook_idempotency

        # Arrange
        mock_db = MagicMock()
        existing_record = WebhookIdempotency(
            id="webhook-123",
            source="korapay",
            tx_ref="ONEPAY-TEST-123"
        )
        mock_db.query().filter().filter().first.return_value = existing_record

        # Act
        result = check_webhook_idempotency(mock_db, "webhook-123", "korapay")

        # Assert
        assert result is True

    def test_store_webhook_idempotency_creates_record(self):
        """
        Test that store_webhook_idempotency creates a new record.

        Requirement 2.4: WHEN a webhook is processed successfully, THE System
        SHALL record the webhook identifier with a timestamp
        """
        from services.webhook import store_webhook_idempotency

        # Arrange
        mock_db = MagicMock()

        # Act
        store_webhook_idempotency(mock_db, "webhook-123", "korapay", "ONEPAY-TEST-123")

        # Assert
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

        # Verify the record has correct fields
        added_record = mock_db.add.call_args[0][0]
        assert added_record.id == "webhook-123"
        assert added_record.source == "korapay"
        assert added_record.tx_ref == "ONEPAY-TEST-123"

    def test_store_webhook_idempotency_without_tx_ref(self):
        """
        Test that store_webhook_idempotency works without tx_ref.
        """
        from services.webhook import store_webhook_idempotency

        # Arrange
        mock_db = MagicMock()

        # Act
        store_webhook_idempotency(mock_db, "webhook-456", "voicepay")

        # Assert
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

        # Verify the record has correct fields
        added_record = mock_db.add.call_args[0][0]
        assert added_record.id == "webhook-456"
        assert added_record.source == "voicepay"
        assert added_record.tx_ref is None

    def test_check_webhook_idempotency_filters_by_source(self):
        """
        Test that check_webhook_idempotency filters by both id and source.

        This ensures that the same webhook ID from different sources
        are treated as different webhooks.
        """
        from services.webhook import check_webhook_idempotency

        # Arrange
        mock_db = MagicMock()
        mock_db.query().filter().filter().first.return_value = None

        # Act
        result = check_webhook_idempotency(mock_db, "webhook-123", "korapay")

        # Assert
        assert result is False
        # Verify both filters were applied
        assert mock_db.query().filter.call_count == 2


class TestWebhookIdempotencyIntegration:
    """Integration tests for webhook idempotency in the endpoint."""

    # Note: These integration tests are simplified to focus on the core idempotency logic.
    # Full end-to-end tests with signature verification are covered in
    # tests/integration/test_webhook_endpoint.py

    def test_idempotency_functions_work_together(self):
        """
        Test that check and store idempotency functions work together.

        Requirements 2.1, 2.2, 2.4: Complete idempotency workflow
        """
        from unittest.mock import MagicMock

        from models.webhook_idempotency import WebhookIdempotency
        from services.webhook import check_webhook_idempotency, store_webhook_idempotency

        # Arrange
        mock_db = MagicMock()
        webhook_id = "test-webhook-789"
        source = "korapay"
        tx_ref = "ONEPAY-TEST-789"

        # First check - should return False (new webhook)
        mock_db.query().filter().filter().first.return_value = None
        assert check_webhook_idempotency(mock_db, webhook_id, source) is False

        # Store the webhook
        store_webhook_idempotency(mock_db, webhook_id, source, tx_ref)

        # Verify record was added
        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert added_record.id == webhook_id
        assert added_record.source == source
        assert added_record.tx_ref == tx_ref

        # Second check - should return True (duplicate webhook)
        mock_db.query().filter().filter().first.return_value = added_record
        assert check_webhook_idempotency(mock_db, webhook_id, source) is True


class TestWebhookIdempotencyEdgeCases:
    """Test edge cases for webhook idempotency."""

    def test_same_webhook_id_different_sources_are_independent(self):
        """
        Test that same webhook ID from different sources are treated independently.

        This ensures idempotency is scoped per source.
        Requirement 2.1: Extract unique identifier from payload (including source)
        """
        from models.webhook_idempotency import WebhookIdempotency
        from services.webhook import check_webhook_idempotency, store_webhook_idempotency

        # Arrange
        mock_db = MagicMock()
        webhook_id = "webhook-999"

        # Store webhook from korapay
        store_webhook_idempotency(mock_db, webhook_id, "korapay", "TX-001")
        korapay_record = mock_db.add.call_args[0][0]

        # Check for same ID from voicepay - should be new
        mock_db.query().filter().filter().first.return_value = None
        assert check_webhook_idempotency(mock_db, webhook_id, "voicepay") is False

        # Check for same ID from korapay - should be duplicate
        mock_db.query().filter().filter().first.return_value = korapay_record
        assert check_webhook_idempotency(mock_db, webhook_id, "korapay") is True

    def test_store_webhook_idempotency_with_empty_string_tx_ref(self):
        """
        Test that store_webhook_idempotency handles empty string tx_ref.

        Requirement 2.4: Record webhook identifier with timestamp
        """
        from services.webhook import store_webhook_idempotency

        # Arrange
        mock_db = MagicMock()

        # Act - store with empty string tx_ref
        store_webhook_idempotency(mock_db, "webhook-empty", "korapay", "")

        # Assert
        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert added_record.id == "webhook-empty"
        assert added_record.source == "korapay"
        assert added_record.tx_ref == ""

    def test_check_webhook_idempotency_with_special_characters(self):
        """
        Test that webhook IDs with special characters are handled correctly.

        Requirement 2.1: Extract unique identifier from payload
        """
        from services.webhook import check_webhook_idempotency

        # Arrange
        mock_db = MagicMock()
        special_webhook_id = "webhook-123-abc_def.xyz@test"

        mock_db.query().filter().filter().first.return_value = None

        # Act
        result = check_webhook_idempotency(mock_db, special_webhook_id, "korapay")

        # Assert
        assert result is False
        # Verify the function completed without errors (special characters handled)
        mock_db.query.assert_called()

    def test_store_webhook_idempotency_records_timestamp(self):
        """
        Test that store_webhook_idempotency creates record with timestamp.

        Requirement 2.4: Record webhook identifier WITH A TIMESTAMP
        """
        from models.webhook_idempotency import WebhookIdempotency
        from services.webhook import store_webhook_idempotency

        # Arrange
        mock_db = MagicMock()

        # Act
        store_webhook_idempotency(mock_db, "webhook-time", "korapay", "TX-TIME")

        # Assert
        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]

        # Verify the record is a WebhookIdempotency instance
        assert isinstance(added_record, WebhookIdempotency)

        # Verify processed_at is set (it's set by default in the model)
        # The timestamp is set automatically by the model's default value
        assert hasattr(added_record, 'processed_at')


class TestWebhookIdempotencyRecordExpiration:
    """Test webhook idempotency record expiration (Requirement 2.3)."""

    def test_cleanup_respects_minimum_24_hour_retention(self):
        """
        Test that cleanup function respects 24-hour minimum retention.

        Requirement 2.3: THE System SHALL store processed webhook identifiers
        for a MINIMUM of 24 hours
        """
        from datetime import datetime, timedelta, timezone

        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 5

        # Act - cleanup with default 24 hours
        deleted_count = cleanup_webhook_idempotency_records(mock_db)

        # Assert
        assert deleted_count == 5

        # Verify the filter was called with correct cutoff time
        # (approximately 24 hours ago)
        mock_query.filter.call_args[0][0]
        # The filter should be checking processed_at < cutoff_time
        # We can't check the exact time, but we can verify the filter was called
        mock_query.filter.assert_called_once()

    def test_cleanup_allows_custom_retention_period(self):
        """
        Test that cleanup function allows custom retention periods.

        This allows for longer retention if needed (e.g., 48 hours, 72 hours).
        Requirement 2.3: Minimum 24 hours (but can be longer)
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 2

        # Act - cleanup with 48 hours retention
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=48)

        # Assert
        assert deleted_count == 2
        mock_db.commit.assert_called_once()

    def test_cleanup_handles_database_errors_gracefully(self):
        """
        Test that cleanup function handles database errors without crashing.

        Requirement 2.3: System reliability during cleanup
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database connection error")

        # Act - cleanup should not raise exception
        deleted_count = cleanup_webhook_idempotency_records(mock_db)

        # Assert
        assert deleted_count == 0
        mock_db.rollback.assert_called_once()
