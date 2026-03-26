"""
OnePay — Background cleanup threads
Periodic cleanup of audit logs and rate limit records to prevent unbounded growth.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)


def start_cleanup_threads():
    """
    Start background daemon threads for periodic cleanup tasks.
    
    Threads:
    - audit-log-cleanup: Removes audit logs older than 90 days
    - rate-limit-cleanup: Removes stale rate limit records older than 1 hour
    """
    
    def _audit_log_cleanup_loop():
        """Background thread that cleans up old audit logs."""
        # Wait a bit for DB to be fully initialized
        time.sleep(10)
        while True:
            try:
                from database import get_db
                from core.audit import cleanup_old_audit_logs
                
                with get_db() as db:
                    cleanup_old_audit_logs(db, retention_days=90)
            except Exception as e:
                logger.error("Audit log cleanup error: %s", e)
            
            # Run every 24 hours
            time.sleep(86400)
    
    def _rate_limit_cleanup_loop():
        """Background thread that cleans up stale rate limit records."""
        # Wait a bit for DB to be fully initialized
        time.sleep(15)
        while True:
            try:
                from database import get_db
                from services.rate_limiter import cleanup_old_rate_limits
                
                with get_db() as db:
                    cleanup_old_rate_limits(db, older_than_secs=3600)
            except Exception as e:
                logger.error("Rate limit cleanup error: %s", e)
            
            # Run every hour
            time.sleep(3600)
    
    # Start audit log cleanup thread
    audit_thread = threading.Thread(
        target=_audit_log_cleanup_loop,
        daemon=True,
        name="audit-log-cleanup"
    )
    audit_thread.start()
    logger.info("Audit log cleanup thread started")
    
    # Start rate limit cleanup thread
    rate_limit_thread = threading.Thread(
        target=_rate_limit_cleanup_loop,
        daemon=True,
        name="rate-limit-cleanup"
    )
    rate_limit_thread.start()
    logger.info("Rate limit cleanup thread started")
