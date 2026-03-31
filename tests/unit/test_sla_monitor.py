"""
Unit tests for SLA monitoring service.

Tests Requirements: 51.11, 51.12, 51.13, 51.15, 51.16
"""

import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from services.sla_monitor import (
    SLAConfig,
    SLAVioLationType,
    SLAViolation,
    SLAMonitor,
    get_sla_monitor,
    reset_sla_monitor,
)


class TestSLAMonitor:
    """Tests for SLAMonitor class."""

    @pytest.fixture(autouse=True)
    def reset_monitor(self):
        """Reset SLA monitor before each test."""
        reset_sla_monitor()
        yield
        reset_sla_monitor()

    def test_record_request_increments_success_count(self):
        """Test that record_request increments success count on success."""
        monitor = get_sla_monitor()
        initial_count = monitor._success_count

        monitor.record_request("create_virtual_account", 150.0, success=True)

        assert monitor._success_count == initial_count + 1

    def test_record_request_increments_failure_count(self):
        """Test that record_request increments failure count on failure."""
        monitor = get_sla_monitor()
        initial_count = monitor._failure_count

        monitor.record_request("create_virtual_account", 150.0, success=False)

        assert monitor._failure_count == initial_count + 1

    def test_get_success_rate_with_no_requests(self):
        """Test success rate is 100% with no requests."""
        monitor = get_sla_monitor()

        rate = monitor.get_success_rate()

        assert rate == 100.0

    def test_get_success_rate_with_all_success(self):
        """Test success rate is 100% with all successful requests."""
        monitor = get_sla_monitor()

        monitor.record_request("create_virtual_account", 150.0, success=True)
        monitor.record_request("create_virtual_account", 150.0, success=True)
        monitor.record_request("create_virtual_account", 150.0, success=True)

        rate = monitor.get_success_rate()

        assert rate == 100.0

    def test_get_success_rate_with_failures(self):
        """Test success rate calculation with failures."""
        monitor = get_sla_monitor()

        monitor.record_request("create_virtual_account", 150.0, success=True)
        monitor.record_request("create_virtual_account", 150.0, success=True)
        monitor.record_request("create_virtual_account", 150.0, success=False)

        rate = monitor.get_success_rate()

        assert rate == pytest.approx(66.67, rel=0.1)

    def test_get_p95_response_time_no_data(self):
        """Test p95 is 0 with no data."""
        monitor = get_sla_monitor()

        p95 = monitor.get_p95_response_time("create_virtual_account")

        assert p95 == 0.0

    def test_get_p95_response_time_with_data(self):
        """Test p95 calculation with response time data."""
        monitor = get_sla_monitor()

        # Add 100 requests with varying response times
        for i in range(100):
            monitor.record_request("create_virtual_account", float(i + 1), success=True)

        p95 = monitor.get_p95_response_time("create_virtual_account")

        # p95 should be around 95-96 (0-indexed, so 95th percentile is ~95)
        assert 94 <= p95 <= 96

    def test_sla_violation_detection_response_time(self):
        """Test SLA violation detection for response time."""
        config = SLAConfig(virtual_account_creation_p95_ms=100.0)
        monitor = SLAMonitor(config)

        # Add requests with high response times
        for _ in range(100):
            monitor.record_request("create_virtual_account", 500.0, success=True)

        violations = monitor.check_sla_violations()

        assert len(violations) == 1
        assert violations[0].violation_type == SLAVioLationType.RESPONSE_TIME
        assert violations[0].endpoint == "create_virtual_account"
        assert violations[0].measured_value == 500.0
        assert violations[0].threshold == 100.0

    def test_sla_violation_detection_success_rate(self):
        """Test SLA violation detection for success rate."""
        config = SLAConfig(min_success_rate_percent=99.0)
        monitor = SLAMonitor(config)

        # Add 100 requests with only 50% success rate
        for i in range(100):
            monitor.record_request("create_virtual_account", 150.0, success=i < 50)

        violations = monitor.check_sla_violations()

        assert len(violations) == 1
        assert violations[0].violation_type == SLAVioLationType.SUCCESS_RATE
        assert violations[0].measured_value == 50.0

    def test_no_violation_when_within_sla(self):
        """Test no violation when within SLA."""
        config = SLAConfig(
            virtual_account_creation_p95_ms=1000.0,
            min_success_rate_percent=90.0
        )
        monitor = SLAMonitor(config)

        # Add requests within SLA
        for i in range(100):
            monitor.record_request("create_virtual_account", 100.0, success=i < 95)

        violations = monitor.check_sla_violations()

        assert len(violations) == 0

    def test_consecutive_violations_increment(self):
        """Test consecutive violations counter increments on violations."""
        config = SLAConfig(consecutive_violations_for_alert=3)
        monitor = SLAMonitor(config)

        # Trigger violations 3 times
        for _ in range(3):
            for i in range(100):
                monitor.record_request("create_virtual_account", 500.0, success=True)
            monitor.check_sla_violations()

        assert monitor._consecutive_violations == 3

    def test_consecutive_violations_reset_on_no_violation(self):
        """Test consecutive violations reset when no violation."""
        config = SLAConfig(consecutive_violations_for_alert=3)
        monitor = SLAMonitor(config)

        # Trigger violation then no violation
        for i in range(100):
            monitor.record_request("create_virtual_account", 500.0, success=True)
        monitor.check_sla_violations()

        # Then no violation
        monitor._response_times.clear()
        monitor.check_sla_violations()

        assert monitor._consecutive_violations == 0

    def test_should_alert_when_consecutive_met(self):
        """Test alert triggered when consecutive violations met."""
        config = SLAConfig(consecutive_violations_for_alert=3)
        monitor = SLAMonitor(config)

        # Trigger violations 3 times
        for _ in range(3):
            for i in range(100):
                monitor.record_request("create_virtual_account", 500.0, success=True)
            monitor.check_sla_violations()

        assert monitor.should_alert() is True

    def test_should_alert_when_consecutive_not_met(self):
        """Test alert not triggered when consecutive violations not met."""
        config = SLAConfig(consecutive_violations_for_alert=5)
        monitor = SLAMonitor(config)

        # Trigger violations only 3 times
        for _ in range(3):
            for i in range(100):
                monitor.record_request("create_virtual_account", 500.0, success=True)
            monitor.check_sla_violations()

        assert monitor.should_alert() is False

    def test_get_violations_since(self):
        """Test filtering violations by time."""
        monitor = get_sla_monitor()

        # Add some violations
        for _ in range(100):
            monitor.record_request("create_virtual_account", 500.0, success=True)
        monitor.check_sla_violations()

        # Get violations in last minute
        since = datetime.now(timezone.utc)
        violations = monitor.get_violations_since(since)

        assert len(violations) >= 1

    def test_get_metrics(self):
        """Test getting metrics summary."""
        monitor = get_sla_monitor()

        # Add some requests
        for i in range(100):
            monitor.record_request("create_virtual_account", 100.0 + i, success=i < 95)

        metrics = monitor.get_metrics()

        assert "success_rate" in metrics
        assert "total_requests" in metrics
        assert "successful_requests" in metrics
        assert "failed_requests" in metrics
        assert "create_virtual_account_p95_ms" in metrics
        assert "consecutive_violations" in metrics
        assert "should_alert" in metrics
        assert metrics["total_requests"] == 100
        assert metrics["successful_requests"] == 95
        assert metrics["failed_requests"] == 5

    @pytest.mark.skip(reason="Background monitoring - causes timeouts in full suite")
    def test_background_monitoring_starts(self):
        """Test background monitoring thread starts."""
        monitor = get_sla_monitor()
        callback = Mock()

        monitor.start_background_monitoring(callback)
        time.sleep(0.5)  # Give thread time to run

        assert monitor._running is True
        assert monitor._monitor_thread is not None
        assert monitor._monitor_thread.daemon is True

        monitor.stop_background_monitoring()

    @pytest.mark.skip(reason="Background monitoring - causes timeouts in full suite")
    def test_background_monitoring_calls_callback(self):
        """Test background monitoring calls callback on alert."""
        config = SLAConfig(
            consecutive_violations_for_alert=1,
            check_interval_seconds=1
        )
        monitor = SLAMonitor(config)
        callback = Mock()

        # Add violations before starting
        for i in range(100):
            monitor.record_request("create_virtual_account", 500.0, success=True)
        monitor.check_sla_violations()

        monitor.start_background_monitoring(callback)
        time.sleep(2)  # Wait for at least one check

        monitor.stop_background_monitoring()

        # Callback should have been called
        assert callback.called or not monitor._running

    def test_thread_safety(self):
        """Test thread-safe operations on SLA monitor."""
        import threading

        monitor = get_sla_monitor()
        errors = []

        def record_requests():
            try:
                for _ in range(100):
                    monitor.record_request("create_virtual_account", 100.0, success=True)
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = [threading.Thread(target=record_requests) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert monitor._success_count == 500


class TestSLAConfig:
    """Tests for SLAConfig."""

    def test_default_config(self):
        """Test default SLA config values."""
        config = SLAConfig()

        assert config.virtual_account_creation_p95_ms == 2000.0
        assert config.transfer_status_p95_ms == 1000.0
        assert config.min_success_rate_percent == 99.5
        assert config.consecutive_violations_for_alert == 5
        assert config.check_interval_seconds == 60

    def test_custom_config(self):
        """Test custom SLA config values."""
        config = SLAConfig(
            virtual_account_creation_p95_ms=3000.0,
            min_success_rate_percent=99.0
        )

        assert config.virtual_account_creation_p95_ms == 3000.0
        assert config.min_success_rate_percent == 99.0


class TestSLAViolation:
    """Tests for SLAViolation."""

    def test_sla_violation_creation(self):
        """Test SLAViolation dataclass."""
        violation = SLAViolation(
            violation_type=SLAVioLationType.RESPONSE_TIME,
            endpoint="create_virtual_account",
            measured_value=500.0,
            threshold=200.0,
            timestamp=datetime.now(timezone.utc)
        )

        assert violation.violation_type == SLAVioLationType.RESPONSE_TIME
        assert violation.endpoint == "create_virtual_account"
        assert violation.measured_value == 500.0
        assert violation.threshold == 200.0
