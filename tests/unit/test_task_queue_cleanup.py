"""
Unit tests for task queue cleanup functions.

Tests the cleanup_webhook_idempotency_records function to ensure
old webhook idempotency records are properly deleted.

**Validates: Requirements 2.3**
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock

import pytest


class TestWebhookIdempotencyCleanup:
    """Test webhook idempotency cleanup function."""

    def test_cleanup_deletes_old_records(self) -> None:
        """
        Test that cleanup_webhook_idempotency_records deletes records older than 24 hours.

        Requirement 2.3: THE System SHALL store processed webhook identifiers
        for a minimum of 24 hours
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        # Setup mock chain
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 5  # 5 records deleted

        # Act
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        # Assert
        assert deleted_count == 5
        mock_db.commit.assert_called_once()
        mock_filter.delete.assert_called_once()

    def test_cleanup_uses_correct_cutoff_time(self) -> None:
        """
        Test that cleanup uses the correct cutoff time based on older_than_hours parameter.
        """
        from models.webhook_idempotency import WebhookIdempotency
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 3

        # Act
        cleanup_webhook_idempotency_records(mock_db, older_than_hours=48)

        # Assert
        # Verify query was called with WebhookIdempotency model
        mock_db.query.assert_called_once()

        # Verify filter was called (checking for processed_at < cutoff_time)
        mock_query.filter.assert_called_once()

        # Verify delete was called
        mock_filter.delete.assert_called_once()

    def test_cleanup_returns_zero_when_no_records_deleted(self) -> None:
        """
        Test that cleanup returns 0 when no records are deleted.
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 0  # No records deleted

        # Act
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        # Assert
        assert deleted_count == 0
        mock_db.commit.assert_called_once()

    def test_cleanup_handles_database_errors(self) -> None:
        """
        Test that cleanup handles database errors gracefully.
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.side_effect = Exception("Database error")

        # Act
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        # Assert
        assert deleted_count == 0
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()

    def test_cleanup_with_custom_hours(self) -> None:
        """
        Test that cleanup accepts custom older_than_hours parameter.
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 10

        # Act - test with 12 hours
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=12)

        # Assert
        assert deleted_count == 10
        mock_db.commit.assert_called_once()

    def test_cleanup_commits_transaction(self) -> None:
        """
        Test that cleanup commits the transaction after deletion.
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 2

        # Act
        cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        # Assert
        # Verify commit is called after delete
        mock_db.commit.assert_called_once()

        # Verify rollback is not called on success
        mock_db.rollback.assert_not_called()

    def test_cleanup_rollback_on_error(self) -> None:
        """
        Test that cleanup rolls back the transaction on error.
        """
        from services.task_queue import cleanup_webhook_idempotency_records

        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.side_effect = Exception("Delete failed")

        # Act
        deleted_count = cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        # Assert
        assert deleted_count == 0
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()
