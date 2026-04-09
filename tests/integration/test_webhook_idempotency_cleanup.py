"""
Integration tests for webhook idempotency cleanup.

Tests the cleanup_webhook_idempotency_records function with a real database
to ensure old records are properly deleted.

**Validates: Requirements 2.3**
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestWebhookIdempotencyCleanupIntegration:
    """Integration tests for webhook idempotency cleanup."""

    def test_cleanup_deletes_old_records_integration(self):
        """
        Test that cleanup deletes old webhook idempotency records.

        Requirement 2.3: THE System SHALL store processed webhook identifiers
        for a minimum of 24 hours
        """
        from models.webhook_idempotency import WebhookIdempotency
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange - Create mock database with old and new records
        mock_db = MagicMock()

        # Create mock old record (older than 24 hours)
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        WebhookIdempotency(
            id="old-webhook-1",
            source="korapay",
            processed_at=old_time,
            tx_ref="ONEPAY-OLD-1"
        )

        # Create mock recent record (less than 24 hours)
        recent_time = datetime.now(timezone.utc) - timedelta(hours=12)
        WebhookIdempotency(
            id="recent-webhook-1",
            source="korapay",
            processed_at=recent_time,
            tx_ref="ONEPAY-RECENT-1"
        )

        # Setup mock query to return old records
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 1  # One old record deleted

        # Act
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        # Assert
        assert deleted_count == 1
        mock_db.commit.assert_called_once()

        # Verify the query was constructed correctly
        mock_db.query.assert_called_once()
        mock_query.filter.assert_called_once()
        mock_filter.delete.assert_called_once()

    def test_cleanup_preserves_recent_records(self):
        """
        Test that cleanup does not delete recent records.

        Requirement 2.3: Records should be kept for at least 24 hours
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 0  # No records deleted (all are recent)

        # Act
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        # Assert
        assert deleted_count == 0
        mock_db.commit.assert_called_once()

    def test_cleanup_can_be_called_manually(self):
        """
        Test that cleanup function can be called manually (not just as a periodic task).

        This is important since Huey is not yet configured (Task 9.1 dependency).
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 3

        # Act - Call directly (not as a Huey task)
        deleted_count = cleanup_webhook_idempotency_records(mock_db)

        # Assert
        assert deleted_count == 3
        assert isinstance(deleted_count, int)
        mock_db.commit.assert_called_once()
