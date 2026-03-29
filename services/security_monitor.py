"""
OnePay — Security Monitoring Service
VULN-011 FIX: Detects and alerts on suspicious activity patterns.
"""
import logging
from datetime import datetime, timedelta, timezone

from models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def detect_suspicious_activity(db) -> list[dict]:
    """
    Analyze recent activity for suspicious patterns.
    
    Args:
        db: Database session
        
    Returns:
        List of detected suspicious activities
    """
    alerts = []
    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)
    
    try:
        # Check for distributed brute force
        failed_logins = db.query(AuditLog).filter(
            AuditLog.event == "merchant.login_failed",
            AuditLog.created_at >= last_hour
        ).count()
        
        if failed_logins > 50:
            alert = {
                "severity": "high",
                "title": "Distributed brute force detected",
                "message": f"{failed_logins} failed logins in 1 hour",
                "timestamp": now.isoformat()
            }
            alerts.append(alert)
            alert_security_team(alert["title"], alert["message"])
        
        # Check for payment link spam
        links_created = db.query(AuditLog).filter(
            AuditLog.event == "link.created",
            AuditLog.created_at >= last_hour
        ).count()
        
        if links_created > 1000:
            alert = {
                "severity": "medium",
                "title": "Unusual link creation volume",
                "message": f"{links_created} links created in 1 hour",
                "timestamp": now.isoformat()
            }
            alerts.append(alert)
            alert_security_team(alert["title"], alert["message"])
        
        # Check for webhook delivery failures
        webhook_failures = db.query(AuditLog).filter(
            AuditLog.event == "webhook.failed",
            AuditLog.created_at >= last_hour
        ).count()
        
        if webhook_failures > 100:
            alert = {
                "severity": "medium",
                "title": "High webhook failure rate",
                "message": f"{webhook_failures} webhook failures in 1 hour",
                "timestamp": now.isoformat()
            }
            alerts.append(alert)
            alert_security_team(alert["title"], alert["message"])
        
        # Check for rate limit violations
        rate_limit_hits = db.query(AuditLog).filter(
            AuditLog.event == "rate_limit.exceeded",
            AuditLog.created_at >= last_hour
        ).count()
        
        if rate_limit_hits > 500:
            alert = {
                "severity": "medium",
                "title": "Excessive rate limit violations",
                "message": f"{rate_limit_hits} rate limit hits in 1 hour",
                "timestamp": now.isoformat()
            }
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
