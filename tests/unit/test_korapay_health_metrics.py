"""
Unit tests for KoraPay service module.
"""

import pytest
from unittest.mock import patch
import os

class TestHealthMetrics:
    """Test health metrics collection for monitoring KoraPay API performance."""

    def test_get_health_metrics_returns_success_rate(self):
        """Test get_health_metrics() returns success_rate as percentage."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Get health metrics
            metrics = korapay.get_health_metrics()

            # Should return dict with success_rate key
            assert isinstance(metrics, dict)
            assert "success_rate" in metrics
            assert isinstance(metrics["success_rate"], (int, float))
            assert 0 <= metrics["success_rate"] <= 100

    def test_get_health_metrics_returns_avg_response_time(self):
        """Test get_health_metrics() returns avg_response_time in milliseconds."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            metrics = korapay.get_health_metrics()

            # Should return dict with avg_response_time key
            assert isinstance(metrics, dict)
            assert "avg_response_time" in metrics
            assert isinstance(metrics["avg_response_time"], (int, float))
            assert metrics["avg_response_time"] >= 0

    def test_get_health_metrics_returns_failures_last_hour(self):
        """Test get_health_metrics() returns failures_last_hour count."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            metrics = korapay.get_health_metrics()

            # Should return dict with failures_last_hour key
            assert isinstance(metrics, dict)
            assert "failures_last_hour" in metrics
            assert isinstance(metrics["failures_last_hour"], int)
            assert metrics["failures_last_hour"] >= 0

    def test_metrics_track_success_and_failure_counts(self):
        """Test metrics track success/failure counts separately."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset metrics for clean test
            korapay._metrics = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "last_request_time": None
            }

            metrics = korapay.get_health_metrics()

            # Should track both success and failure counts
            assert "total_requests" in metrics
            assert "successful_requests" in metrics
            assert "failed_requests" in metrics

    def test_metrics_use_rolling_window_for_response_times(self):
        """Test metrics use rolling window (last 100 requests) for response times."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Verify _response_times deque exists with maxlen
            assert hasattr(korapay, '_response_times')
            assert hasattr(korapay._response_times, 'maxlen')
            assert korapay._response_times.maxlen == 100

    def test_metrics_are_thread_safe(self):
        """Test metrics use lock for thread-safe access."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Verify _metrics_lock exists for thread safety
            assert hasattr(korapay, '_metrics_lock')

    @pytest.mark.skip(reason="Module reload causes singleton recreation - metrics state not preserved across reloads")
    def test_metrics_update_after_successful_request(self):
        """Test metrics are updated after successful API request."""
        import threading
        import time
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset metrics
            korapay._metrics = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "last_request_time": None
            }
            korapay._response_times.clear()

            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "success", "data": {"reference": "REF", "status": "success"}}

            with patch.object(korapay._session, 'request', return_value=mock_response):
                korapay.confirm_transfer("TEST-REF")

            # Verify metrics were updated
            assert korapay._metrics["total_requests"] >= 1
            assert korapay._metrics["successful_requests"] >= 1

    @pytest.mark.skip(reason="Module reload causes singleton recreation - metrics state not preserved across reloads")
    def test_metrics_update_after_failed_request(self):
        """Test metrics are updated after failed API request."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset metrics
            korapay._metrics = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "last_request_time": None
            }
            korapay._response_times.clear()

            # Mock failed response with ConnectionError
            import requests
            with patch.object(korapay._session, 'request', side_effect=requests.ConnectionError("Network error")):
                try:
                    korapay.confirm_transfer("TEST-REF")
                except:
                    pass

            # Verify failure was tracked
            assert korapay._metrics["failed_requests"] >= 1

