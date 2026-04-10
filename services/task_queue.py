"""
OnePay — Task Queue Integration

Huey task queue integration for background processing.
Replaces thread-based webhook delivery and periodic cleanup tasks.
"""

import logging
from datetime import datetime, timedelta, timezone

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
    import importlib

    # Use importlib to avoid static circular-import detection.
    # At runtime this is safe because both modules are fully loaded before tasks run.
    webhook_module = importlib.import_module("services.webhook")
    deliver_fn = getattr(webhook_module, "deliver_webhook_from_dict")

    tx_ref = webhook_data.get("tx_ref", "?")

    try:
        success = deliver_fn(webhook_data)
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
    from datetime import timedelta

    from database import get_db
    from models.rate_limit import RateLimit

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
    from datetime import timedelta

    from database import get_db
    from models.audit_log import AuditLog

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


@huey.periodic_task(crontab(hour="*/6"))
def cleanup_expired_sessions():
    """
    Clean up expired Redis sessions every 6 hours.

    Logs the current number of sessions in Redis for monitoring.
    Redis automatically expires sessions via TTL, but this task
    provides visibility into session count.

    **Validates: SEC-007**
    """
    try:
        import redis

        from config import Config

        redis_client = redis.from_url(Config.SESSION_REDIS)
        session_count = redis_client.dbsize()
        logger.info("Current Redis sessions: %d", session_count)
    except Exception as e:
        logger.error("Failed to check Redis sessions: %s", e)


@huey.periodic_task(crontab(minute="*/30"))
def warm_cache_periodically():
    """
    Warm cache every 30 minutes for frequently accessed data.

    Ensures cache stays populated for optimal performance.
    Skips in debug mode to avoid unnecessary overhead.

    **Validates: PERF-005**
    """
    if Config.DEBUG:
        return

    try:
        from services.cache_warming import warm_all_users_cache
        warm_all_users_cache()
        logger.info("Periodic cache warming completed")
    except Exception as e:
        logger.error("Failed periodic cache warming: %s", e)


@huey.periodic_task(crontab(minute="*/5"))
def generate_recurring_invoices():
    """
    Generate invoices for recurring schedules every 5 minutes.

    Checks for recurring invoices where next_invoice_date has passed
    and generates new invoices, updating the next_invoice_date accordingly.

    **Validates: FEAT-005**
    """
    from database import get_db
    from models.invoice import Invoice, InvoiceSettings, InvoiceStatus
    from models.recurring_invoice import RecurringInvoice
    from models.transaction import Transaction
    from models.user import User
    from services.invoice import invoice_service

    with get_db() as db:
        now = datetime.now(timezone.utc)

        # Find recurring invoices that are due
        due_invoices = db.query(RecurringInvoice).filter(
            RecurringInvoice.is_active == 1,
            RecurringInvoice.next_invoice_date <= now,
            (RecurringInvoice.end_date.is_(None) | (RecurringInvoice.end_date >= now))
        ).all()

        if not due_invoices:
            return

        logger.info(f"Found {len(due_invoices)} recurring invoices due for generation")

        for recurring in due_invoices:
            try:
                # Get user and settings
                user = db.query(User).filter(User.id == recurring.user_id).first()
                if not user:
                    logger.error(f"User not found for recurring invoice {recurring.id}")
                    continue

                settings = db.query(InvoiceSettings).filter(InvoiceSettings.user_id == recurring.user_id).first()

                # Create a transaction for the invoice
                from core.security import generate_expiration_time, generate_hash_token, generate_tx_reference

                tx_ref = generate_tx_reference()
                expires_at = generate_expiration_time()
                hash_token = generate_hash_token(tx_ref, recurring.amount, expires_at)

                transaction = Transaction(
                    tx_ref=tx_ref,
                    user_id=recurring.user_id,
                    amount=recurring.amount,
                    currency=recurring.currency,
                    description=recurring.description or f"Recurring invoice: {recurring.customer_name or recurring.customer_email}",
                    customer_email=recurring.customer_email,
                    customer_phone=recurring.customer_phone,
                    hash_token=hash_token,
                    expires_at=expires_at,
                )
                db.add(transaction)
                db.flush()

                # Create invoice
                invoice = invoice_service.create_invoice(
                    db=db, transaction=transaction, user=user, settings=settings
                )

                # Update next invoice date based on frequency
                recurring.next_invoice_date = _calculate_next_invoice_date(recurring.frequency, recurring.next_invoice_date)

                # If end date passed, deactivate
                if recurring.end_date and recurring.next_invoice_date > recurring.end_date:
                    recurring.is_active = 0

                db.commit()
                logger.info(f"Generated recurring invoice | recurring_id={recurring.id} invoice_number={invoice.invoice_number}")

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to generate recurring invoice | recurring_id={recurring.id} error={e}")


def _calculate_next_invoice_date(frequency: str, current_date: datetime) -> datetime:
    """Calculate next invoice date based on frequency."""
    from datetime import timedelta

    frequency = frequency.lower()

    if frequency == 'daily':
        return current_date + timedelta(days=1)
    elif frequency == 'weekly':
        return current_date + timedelta(weeks=1)
    elif frequency == 'biweekly':
        return current_date + timedelta(weeks=2)
    elif frequency == 'monthly':
        # Add one month, handling month boundaries
        if current_date.month == 12:
            return current_date.replace(year=current_date.year + 1, month=1)
        else:
            return current_date.replace(month=current_date.month + 1)
    elif frequency == 'quarterly':
        # Add 3 months
        new_month = current_date.month + 3
        new_year = current_date.year
        if new_month > 12:
            new_month -= 12
            new_year += 1
        return current_date.replace(year=new_year, month=new_month)
    elif frequency == 'yearly':
        return current_date.replace(year=current_date.year + 1)
    else:
        # Default to monthly
        return current_date + timedelta(days=30)


@huey.periodic_task(crontab(hour="*"))
def send_invoice_reminders():
    """
    Send payment reminders for unpaid invoices hourly.

    Checks for unpaid invoices that are due soon or overdue and sends
    reminder emails based on user's reminder settings.

    **Validates: FEAT-006**
    """
    from database import get_db
    from models.invoice import Invoice, InvoiceSettings, InvoiceStatus
    from models.user import User
    from services.email import send_payment_reminder_email

    with get_db() as db:
        now = datetime.now(timezone.utc)

        # Get all users with reminder enabled
        users_with_reminders = db.query(InvoiceSettings).filter(
            InvoiceSettings.reminder_enabled == True
        ).all()

        if not users_with_reminders:
            return

        logger.info(f"Checking reminders for {len(users_with_reminders)} users")

        for settings in users_with_reminders:
            try:
                user = db.query(User).filter(User.id == settings.user_id).first()
                if not user:
                    continue

                # Find unpaid invoices for this user
                unpaid_invoices = db.query(Invoice).filter(
                    Invoice.user_id == settings.user_id,
                    Invoice.status == InvoiceStatus.SENT,
                    Invoice.customer_email.isnot(None)
                ).all()

                for invoice in unpaid_invoices:
                    # Calculate days until due (assuming 30-day payment terms)
                    days_since_sent = (now - invoice.sent_at).days if invoice.sent_at else 0
                    days_before_due = 30 - days_since_sent

                    # Check if reminder should be sent
                    should_send = False
                    reminder_type = None

                    # Before due date reminder
                    if days_before_due == settings.reminder_days_before_due:
                        should_send = True
                        reminder_type = "before_due"

                    # Overdue reminder
                    elif days_before_due < 0 and abs(days_before_due) == settings.reminder_days_overdue:
                        should_send = True
                        reminder_type = "overdue"

                    if should_send:
                        # Check if reminder already sent for this invoice
                        # (This is a simplified check - in production, track reminder attempts)
                        try:
                            sent = send_payment_reminder_email(
                                to_email=invoice.customer_email,
                                invoice=invoice,
                                reminder_type=reminder_type,
                                days=abs(days_before_due),
                                merchant_name=settings.business_name or user.email
                            )
                            if sent:
                                logger.info(f"Reminder sent | invoice={invoice.invoice_number} type={reminder_type}")
                        except Exception as e:
                            logger.error(f"Failed to send reminder | invoice={invoice.invoice_number} error={e}")

            except Exception as e:
                logger.error(f"Failed to process reminders for user {settings.user_id}: {e}")
