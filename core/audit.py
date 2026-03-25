"""
OnePay — Audit logging helper
Provides a simple interface for logging security-relevant events.
"""
import json
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_event(
    db: Session,
    event: str,
    user_id: Optional[int] = None,
    tx_ref: Optional[str] = None,
    ip_address: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a security-relevant event to the audit log.
    
    Args:
        db: Database session
        event: Event name (e.g., "merchant.login", "link.created")
        user_id: User ID if applicable
        tx_ref: Transaction reference if applicable
        ip_address: Client IP address if applicable
        detail: Additional structured data (will be JSON-encoded)
    """
    try:
        detail_json = json.dumps(detail) if detail else None
        
        audit = AuditLog(
            event=event,
            user_id=user_id,
            tx_ref=tx_ref,
            ip_address=ip_address,
            detail=detail_json,
        )
        db.add(audit)
        db.flush()
        
        logger.debug("Audit event logged: %s (user=%s, tx=%s)", event, user_id, tx_ref)
    except Exception as e:
        logger.error("Failed to log audit event %s: %s", event, e, exc_info=True)
        # Don't raise — audit logging should never break the main flow


def cleanup_old_audit_logs(db: Session, retention_days: int = 90) -> int:
    """
    Delete audit logs older than retention_days.
    
    Args:
        db: Database session
        retention_days: Number of days to retain logs (default 90)
    
    Returns:
        Number of records deleted
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()
        if deleted:
            logger.info("Cleaned up %d old audit log records", deleted)
        return deleted
    except Exception as e:
        logger.error("Failed to cleanup audit logs: %s", e, exc_info=True)
        return 0
