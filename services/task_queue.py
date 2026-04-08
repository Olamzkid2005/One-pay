"""
OnePay — Task Queue Integration

Huey task queue integration for background processing.
Replaces thread-based webhook delivery and periodic cleanup tasks.
"""

import logging
from datetime import datetime, timezone, timedelta
from huey import SqliteHuey, crontab
from config import Config

logger = logging.getLogger(__name__)

# Initialize Huey with SQLite (lightweight, no Redis dependency)
huey = SqliteHuey(
    filename=Config.HUEY_DB_PATH if hasattr(Config, 'HUEY_DB_PATH') else 'huey.db',
    results=True,
    store_errors=True,
    immediate=Config.DEBUG  # Run tasks synchronously in debug mode
)


def cleanup_webhook_idempotency_records(db, older_than_hours: int = 24) -> int:
    """
    Delete webhook idempotency records older than specified hours.
    
    Args:
        db: Database session
        older_than_hours: Delete records older than this many hours (default: 24)
    
    Returns:
        Number of records deleted
    """
    from models.webhook_idempotency import WebhookIdempotency
    
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    
    try:
        deleted_count = db.query(WebhookIdempotency).filter(
            WebhookIdempotency.processed_at < cutoff_time
        ).delete()
        
        db.commit()
        
        if deleted_count > 0:
            logger.info(
                "Cleaned up webhook idempotency records | count=%d older_than=%dh",
                deleted_count,
                older_than_hours
            )
        
        return deleted_count
        
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to cleanup webhook idempotency records | error=%s",
            str(e)
        )
        return 0


def get_db():
    """Lazy import to avoid circular dependency."""
    from database import get_db as _get_db
    return _get_db()


@huey.task(retries=Config.WEBHOOK_MAX_RETRIES, retry_delay=60)
def deliver_webhook_task(webhook_data: dict):
    """
    Deliver webhook in background with automatic retries.

    Replaces thread-based webhook delivery with Huey task queue.
    Uses exponential backoff for retries (handled by Huey).

    Args:
        webhook_data: Dict with tx_ref, webhook_url, amount, currency, status, etc.

    Returns:
        bool: True on success, False on failure

    **Validates: Requirements 10.2**
    """
    from services.webhook import deliver_webhook_from_dict

    tx_ref = webhook_data.get("tx_ref", "?")

    try:
        success = deliver_webhook_from_dict(webhook_data)
        if success:
            logger.info("Webhook delivered successfully | tx_ref=%s", tx_ref)
            return True
        else:
            # deliver_webhook_from_dict already logged the failure
            # Raise exception to trigger Huey retry
            raise Exception("Webhook delivery failed after retries")
    except Exception as e:
        logger.error(
            "Webhook task failed | tx_ref=%s error=%s",
            tx_ref,
            str(e)
        )
        raise  # Re-raise to let Huey handle retry logic


@huey.periodic_task(crontab(minute="*/5"))
def cleanup_rate_limits():
    """
    Clean up expired rate limit records every 5 minutes.

    Removes rate limit entries older than 1 hour to prevent
    database bloat from expired rate limit tracking.

    **Validates: Requirements 10.3**
    """
    from database import get_db
    from models.rate_limit import RateLimit
    from datetime import timedelta

    with get_db() as db:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            deleted = (
                db.query(RateLimit)
                .filter(RateLimit.created_at < cutoff)
                .delete(synchronize_session=False)
            )
            db.commit()
            if deleted:
                logger.info("Cleaned up %d expired rate limit records", deleted)
        except Exception as e:
            db.rollback()
            logger.error("Failed to cleanup rate limits: %s", e)


@huey.periodic_task(crontab(hour="*"))
def cleanup_audit_logs():
    """
    Clean up audit logs older than 90 days (hourly check).

    Prevents audit_logs table from growing unbounded while
    retaining 90 days of audit trail for compliance.

    **Validates: Requirements 10.3**
    """
    from database import get_db
    from models.audit_log import AuditLog
    from datetime import timedelta

    with get_db() as db:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            deleted = (
                db.query(AuditLog)
                .filter(AuditLog.created_at < cutoff)
                .delete(synchronize_session=False)
            )
            db.commit()
            if deleted:
                logger.info("Cleaned up %d audit logs older than 90 days", deleted)
        except Exception as e:
            db.rollback()
            logger.error("Failed to cleanup audit logs: %s", e)


@huey.periodic_task(crontab(hour="*"))
def cleanup_webhook_idempotency_task():
    """
    Clean up webhook idempotency records older than 24 hours (hourly check).

    Prevents webhook_idempotency table from growing unbounded while
    ensuring duplicates are caught within a reasonable time window.

    **Validates: Requirements 10.3**
    """
    with get_db() as db:
        cleanup_webhook_idempotency_records(db, older_than_hours=24)
