"""
SLA Monitoring Service for KoraPay Integration

This module provides SLA monitoring capabilities including:
- Tracking SLA metrics (success rate, response time)
- Detecting SLA violations
- Sending alerts on violations

Requirements: 51.11-51.18
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SLAVioLationType(Enum):
    """Types of SLA violations."""
    RESPONSE_TIME = "response_time"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"


@dataclass
class SLAConfig:
    """SLA configuration for KoraPay endpoints."""
    virtual_account_creation_p95_ms: float = 2000.0
    transfer_status_p95_ms: float = 1000.0
    min_success_rate_percent: float = 99.5
    consecutive_violations_for_alert: int = 5
    check_interval_seconds: int = 60


@dataclass
class SLAViolation:
    """Represents an SLA violation."""
    violation_type: SLAVioLationType
    endpoint: str
    measured_value: float
    threshold: float
    timestamp: datetime


class SLAMonitor:
    """
    SLA Monitor for tracking KoraPay API performance.

    Tracks:
    - Response times for API calls
    - Success/failure counts
    - SLA violations over time

    Sends alerts when violations persist for configured consecutive periods.
    """

    def __init__(self, config: Optional[SLAConfig] = None):
        """
        Initialize SLA Monitor.

        Args:
            config: SLA configuration. Uses defaults if not provided.
        """
        self.config = config or SLAConfig()
        self._response_times = deque(maxlen=1000)
        self._success_count = 0
        self._failure_count = 0
        self._lock = threading.Lock()
        self._violations = deque(maxlen=100)
        self._consecutive_violations = 0
        self._last_check_time = time.time()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def record_request(self, endpoint: str, duration_ms: float, success: bool):
        """
        Record an API request for SLA tracking.

        Args:
            endpoint: API endpoint name
            duration_ms: Request duration in milliseconds
            success: Whether request succeeded
        """
        with self._lock:
            self._response_times.append({
                "endpoint": endpoint,
                "duration_ms": duration_ms,
                "success": success,
                "timestamp": datetime.now(timezone.utc)
            })

            if success:
                self._success_count += 1
            else:
                self._failure_count += 1

    def get_success_rate(self) -> float:
        """
        Get current success rate as percentage.

        Returns:
            Success rate 0-100
        """
        with self._lock:
            total = self._success_count + self._failure_count
            if total == 0:
                return 100.0
            return (self._success_count / total) * 100

    def get_p95_response_time(self, endpoint: str) -> float:
        """
        Get p95 response time for endpoint in milliseconds.

        Args:
            endpoint: API endpoint name

        Returns:
            p95 response time in ms, or 0 if no data
        """
        with self._lock:
            endpoint_times = [r["duration_ms"] for r in self._response_times if r["endpoint"] == endpoint]

            if not endpoint_times:
                return 0.0

            sorted_times = sorted(endpoint_times)
            p95_index = int(len(sorted_times) * 0.95)
            return sorted_times[p95_index]

    def check_sla_violations(self) -> list[SLAViolation]:
        """
        Check for current SLA violations.

        Returns:
            List of current SLA violations
        """
        violations = []

        with self._lock:
            # Check virtual account creation SLA
            va_p95 = self.get_p95_response_time("create_virtual_account")
            if va_p95 > self.config.virtual_account_creation_p95_ms:
                violations.append(SLAViolation(
                    violation_type=SLAVioLationType.RESPONSE_TIME,
                    endpoint="create_virtual_account",
                    measured_value=va_p95,
                    threshold=self.config.virtual_account_creation_p95_ms,
                    timestamp=datetime.now(timezone.utc)
                ))

            # Check transfer status SLA
            ts_p95 = self.get_p95_response_time("confirm_transfer")
            if ts_p95 > self.config.transfer_status_p95_ms:
                violations.append(SLAViolation(
                    violation_type=SLAVioLationType.RESPONSE_TIME,
                    endpoint="confirm_transfer",
                    measured_value=ts_p95,
                    threshold=self.config.transfer_status_p95_ms,
                    timestamp=datetime.now(timezone.utc)
                ))

            # Check success rate SLA
            success_rate = self.get_success_rate()
            if success_rate < self.config.min_success_rate_percent:
                violations.append(SLAViolation(
                    violation_type=SLAVioLationType.SUCCESS_RATE,
                    endpoint="all",
                    measured_value=success_rate,
                    threshold=self.config.min_success_rate_percent,
                    timestamp=datetime.now(timezone.utc)
                ))

        # Update violation tracking
        if violations:
            self._consecutive_violations += 1
            self._violations.extend(violations)
            logger.warning(f"SLA violations detected: {len(violations)}, consecutive: {self._consecutive_violations}")
        else:
            self._consecutive_violations = 0
            logger.debug("No SLA violations detected")

        return violations

    def should_alert(self) -> bool:
        """
        Check if alert should be triggered.

        Returns:
            True if alert should be sent
        """
        return self._consecutive_violations >= self.config.consecutive_violations_for_alert

    def get_violations_since(self, since: datetime) -> list[SLAViolation]:
        """
        Get violations since a given time.

        Args:
            since: Start time

        Returns:
            List of violations since time
        """
        with self._lock:
            return [v for v in self._violations if v.timestamp >= since]

    def get_metrics(self) -> dict:
        """
        Get current SLA metrics.

        Returns:
            Dict with current metrics
        """
        with self._lock:
            return {
                "success_rate": round(self.get_success_rate(), 2),
                "total_requests": self._success_count + self._failure_count,
                "successful_requests": self._success_count,
                "failed_requests": self._failure_count,
                "create_virtual_account_p95_ms": round(self.get_p95_response_time("create_virtual_account"), 2),
                "confirm_transfer_p95_ms": round(self.get_p95_response_time("confirm_transfer"), 2),
                "consecutive_violations": self._consecutive_violations,
                "should_alert": self.should_alert()
            }

    def start_background_monitoring(self, alert_callback=None):
        """
        Start background thread for SLA monitoring.

        Args:
            alert_callback: Function to call when alert should be sent
        """
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(alert_callback,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("SLA monitoring started")

    def stop_background_monitoring(self):
        """Stop background SLA monitoring thread."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("SLA monitoring stopped")

    def _monitor_loop(self, alert_callback):
        """Background monitoring loop."""
        while self._running:
            try:
                violations = self.check_sla_violations()
                if violations and self.should_alert() and alert_callback:
                    alert_callback(violations)
                    self._consecutive_violations = 0
            except Exception as e:
                logger.error(f"Error in SLA monitoring loop: {e}")

            time.sleep(self.config.check_interval_seconds)


# Global SLA monitor instance
_sla_monitor: Optional[SLAMonitor] = None
_sla_monitor_lock = threading.Lock()


def get_sla_monitor() -> SLAMonitor:
    """
    Get global SLA monitor instance.

    Returns:
        SLA monitor singleton
    """
    global _sla_monitor
    with _sla_monitor_lock:
        if _sla_monitor is None:
            _sla_monitor = SLAMonitor()
        return _sla_monitor


def reset_sla_monitor():
    """Reset global SLA monitor (for testing)."""
    global _sla_monitor
    with _sla_monitor_lock:
        if _sla_monitor:
            _sla_monitor.stop_background_monitoring()
        _sla_monitor = None
