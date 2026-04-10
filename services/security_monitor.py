"""
OnePay — Security Monitoring Service
VULN-011 FIX: Detects and alerts on suspicious activity patterns.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def _check_threshold(
    db, event: str, since, threshold: int, severity: str, title: str, unit: str, now
) -> Optional[dict]:
    """Count audit events since `since` and return an alert dict if threshold exceeded."""
    count = db.query(AuditLog).filter(AuditLog.event == event, AuditLog.created_at >= since).count()
    if count > threshold:
        return {
            "severity": severity,
            "title": title,
            "message": f"{count} {unit} in 1 hour",
            "timestamp": now.isoformat(),
        }
    return None


def detect_suspicious_activity(db) -> list[dict]:
    """Analyze recent activity for suspicious patterns. Returns list of alert dicts."""
    alerts = []
    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)

    checks = [
        ("merchant.login_failed", 50, "high", "Distributed brute force detected", "failed logins"),
        ("link.created", 1000, "medium", "Unusual link creation volume", "links created"),
        ("webhook.failed", 100, "medium", "High webhook failure rate", "webhook failures"),
        ("rate_limit.exceeded", 500, "medium", "Excessive rate limit violations", "rate limit hits"),
    ]

    try:
        for event, threshold, severity, title, unit in checks:
            alert = _check_threshold(db, event, last_hour, threshold, severity, title, unit, now)
            if alert:
                alerts.append(alert)
                alert_security_team(alert["title"], alert["message"])
        return alerts
    except Exception as e:
        logger.error("Security monitoring error: %s", e)
        return []


def alert_security_team(title: str, message: str):
    """
    Send alert to security team via logging.

    TODO: Integrate with email/Slack/PagerDuty for production alerting.

    Args:
        title: Alert title
        message: Alert message
    """
    logger.critical("SECURITY ALERT: %s - %s", title, message)
    # TODO: Add email/Slack/PagerDuty integration
