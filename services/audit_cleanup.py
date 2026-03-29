"""
OnePay — Audit Log Cleanup Service
VULN-010 FIX: Implements audit log retention policy to prevent database bloat.
"""
import logging
from datetime import datetime, timedelta, timezone

from models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def cleanup_old_audit_logs(db, retention_days: int = 90) -> int:
    """
    Delete audit logs older than retention period.
    
    Args:
        db: Database session
        retention_days: Number of days to retain logs (default: 90)
        
    Returns:
        Number of deleted records
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    try:
        deleted_count = db.query(AuditLog).filter(
            AuditLog.created_at < cutoff
        ).delete(synchronize_session=False)
        
        db.commit()
        
        if deleted_count:
            logger.info("Cleaned up %d old audit log entries (older than %d days)", 
                       deleted_count, retention_days)
        
        return deleted_count
        
    except Exception as e:
        logger.error("Audit cleanup error: %s", e)
        db.rollback()
        raise
