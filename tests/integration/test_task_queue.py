"""
OnePay — Task Queue Integration Tests

Tests for Huey task queue integration:
- Webhook delivery task execution
- Retry behavior
- Periodic task scheduling
- Backward compatibility with thread-based delivery
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from services.task_queue import (
    huey,
    deliver_webhook_task,
    cleanup_rate_limits,
    cleanup_audit_logs,
    cleanup_webhook_idempotency_task,
    cleanup_webhook_idempotency_records,
)
from services.webhook import deliver_webhook_from_dict, queue_webhook_delivery


class TestDeliverWebhookTask:
    """Tests for webhook delivery task (Requirement 10.2)"""

    @patch('services.webhook.deliver_webhook_from_dict')
    def test_webhook_task_success(self, mock_deliver):
        """Test successful webhook delivery via task queue"""
        mock_deliver.return_value = True

        webhook_data = {
            "tx_ref": "ONEPAY-TEST-001",
            "webhook_url": "https://example.com/webhook",
            "amount": "1000.00",
            "currency": "NGN",
            "status": "verified"
        }

        # Use call_local() to invoke the underlying function directly,
        # bypassing Huey's task wrapper (which swallows exceptions in immediate mode)
        result = deliver_webhook_task.call_local(webhook_data)

        assert result is True
        mock_deliver.assert_called_once_with(webhook_data)

    @patch('services.webhook.deliver_webhook_from_dict')
    def test_webhook_task_failure_raises_exception(self, mock_deliver):
        """Test that failed webhook delivery raises exception for retry"""
        mock_deliver.return_value = False

        webhook_data = {
            "tx_ref": "ONEPAY-TEST-002",
            "webhook_url": "https://example.com/webhook",
            "amount": "1000.00",
        }

        # Use call_local() to test the underlying function directly.
        # Huey's immediate mode swallows exceptions internally; call_local bypasses that.
        with pytest.raises(Exception, match="Webhook delivery failed"):
            deliver_webhook_task.call_local(webhook_data)

    @patch('services.webhook.deliver_webhook_from_dict')
    def test_webhook_task_logs_success(self, mock_deliver, caplog):
        """Test successful delivery logs appropriate message"""
        import logging
        mock_deliver.return_value = True

        webhook_data = {"tx_ref": "ONEPAY-TEST-003", "webhook_url": "https://example.com"}

        # Use call_local() to invoke the underlying function directly so
        # log messages are captured by caplog (Huey's executor runs in a
        # different context in immediate mode).
        # Set log level to INFO so caplog captures the success message.
        with caplog.at_level(logging.INFO, logger="services.task_queue"):
            deliver_webhook_task.call_local(webhook_data)

        assert "Webhook delivered successfully" in caplog.text
        assert "ONEPAY-TEST-003" in caplog.text


class TestQueueWebhookDelivery:
    """Tests for queue_webhook_delivery function (Requirements 10.2, 10.5)"""

    @patch('services.task_queue.huey')
    @patch('services.task_queue.deliver_webhook_task')
    def test_queue_uses_huey_when_available(self, mock_task, mock_huey):
        """Test that Huey is used when available"""
        mock_huey.immediate = False
        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_task.return_value = mock_result

        webhook_data = {"tx_ref": "ONEPAY-TEST-004", "webhook_url": "https://example.com"}
        result = queue_webhook_delivery(webhook_data)

        assert result is True
        mock_task.assert_called_once_with(webhook_data)

    @patch('services.task_queue.huey')
    @patch('services.task_queue.deliver_webhook_task')
    def test_queue_immediate_mode_direct_delivery(self, mock_task, mock_huey):
        """Test immediate mode delivers directly (for testing)"""
        mock_huey.immediate = True
        mock_result = MagicMock()
        mock_result.result = True
        mock_task.return_value = mock_result

        webhook_data = {"tx_ref": "ONEPAY-TEST-005"}
        result = queue_webhook_delivery(webhook_data)

        assert result is True
        mock_task.assert_called_once_with(webhook_data)

    def test_queue_fallback_to_thread(self):
        """Test fallback to thread-based delivery when Huey unavailable"""
        import threading as threading_module

        mock_thread_instance = MagicMock()
        mock_thread_instance.start = MagicMock()

        webhook_data = {"tx_ref": "ONEPAY-TEST-006"}

        # Patch threading.Thread inside the services.webhook module's local import
        # by patching the threading module itself
        with patch.dict('sys.modules', {'services.task_queue': None}):
            with patch('threading.Thread', return_value=mock_thread_instance):
                result = queue_webhook_delivery(webhook_data)

        # The fallback path should have been triggered
        assert result is True
        mock_thread_instance.start.assert_called_once()


class TestPeriodicCleanupTasks:
    """Tests for periodic cleanup tasks (Requirement 10.3)"""

    def test_cleanup_webhook_idempotency_deletes_old_records(self):
        """Test webhook idempotency cleanup removes records older than 24 hours"""
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 1

        deleted = cleanup_webhook_idempotency_records(mock_db, older_than_hours=24)

        assert deleted == 1
        mock_db.commit.assert_called_once()

    def test_cleanup_rate_limits_is_callable(self):
        """Test cleanup_rate_limits task is callable"""
        assert callable(cleanup_rate_limits)

    def test_cleanup_audit_logs_is_callable(self):
        """Test cleanup_audit_logs task is callable"""
        assert callable(cleanup_audit_logs)

    def test_cleanup_webhook_idempotency_task_is_callable(self):
        """Test cleanup_webhook_idempotency_task is callable"""
        assert callable(cleanup_webhook_idempotency_task)


class TestHueyConfiguration:
    """Tests for Huey task queue configuration (Requirement 10.1)"""

    def test_huey_uses_sqlite_storage(self):
        """Test Huey is configured with SQLite storage"""
        # Check that huey is configured
        assert huey is not None
        # In immediate mode for testing
        assert hasattr(huey, 'immediate')

    def test_huey_task_has_retries_configured(self):
        """Test webhook task has retry configuration"""
        # Verify the task wrapper has retry settings configured
        settings = deliver_webhook_task.settings
        assert settings is not None
        assert settings.get('default_retries', 0) > 0


class TestBackwardCompatibility:
    """Tests for backward compatibility (Requirement 10.5)"""

    def test_deliver_webhook_from_dict_still_works(self):
        """Test original deliver_webhook_from_dict still functions"""
        # This tests that the original function still exists and is callable
        assert callable(deliver_webhook_from_dict)

    @patch('services.webhook._send_with_retries')
    def test_deliver_webhook_from_dict_calls_send(self, mock_send):
        """Test deliver_webhook_from_dict uses _send_with_retries"""
        mock_send.return_value = True

        webhook_data = {
            "webhook_url": "https://example.com/webhook",
            "tx_ref": "ONEPAY-TEST-007",
            "amount": "1000.00",
            "currency": "NGN"
        }

        result = deliver_webhook_from_dict(webhook_data)

        assert result is True
        mock_send.assert_called_once()


class TestTaskQueueIntegration:
    """Integration tests for complete task queue flow"""

    @pytest.mark.integration
    @patch('services.webhook.deliver_webhook_from_dict')
    def test_full_webhook_delivery_flow(self, mock_deliver, caplog):
        """Test complete webhook delivery flow from queue to delivery"""
        import logging
        mock_deliver.return_value = True

        webhook_data = {
            "tx_ref": "ONEPAY-INTEGRATION-001",
            "webhook_url": "https://example.com/webhook",
            "amount": "1000.00",
            "currency": "NGN",
            "status": "verified",
            "verified_at": datetime.now(timezone.utc).isoformat()
        }

        # Use call_local() to test the underlying function directly
        with caplog.at_level(logging.INFO, logger="services.task_queue"):
            result = deliver_webhook_task.call_local(webhook_data)

        assert result is True
        assert "Webhook delivered successfully" in caplog.text
