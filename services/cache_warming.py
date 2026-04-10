"""
Cache Warming Service for OnePay

Pre-loads frequently accessed data into cache to improve performance.
"""
import logging

from database import get_db
from models.invoice import InvoiceSettings
from models.transaction import Transaction
from models.user import User
from services.cache import cache_set

logger = logging.getLogger(__name__)


def warm_user_cache(user_id: int):
    """
    Warm cache for a specific user's data.

    Args:
        user_id: User ID to warm cache for
    """
    try:
        with get_db() as db:
            # Recent transactions (last 10)
            recent_tx = (
                db.query(Transaction)
                .filter_by(user_id=user_id)
                .order_by(Transaction.created_at.desc())
                .limit(10)
                .all()
            )
            cache_set(
                f"user:{user_id}:recent_tx",
                [tx.to_dict() for tx in recent_tx],
                ttl=300,
                tags=[f"user:{user_id}", "transactions"]
            )

            # Invoice settings
            settings = db.query(InvoiceSettings).filter_by(user_id=user_id).first()
            if settings:
                cache_set(
                    f"user:{user_id}:invoice_settings",
                    settings.to_dict(),
                    ttl=3600,
                    tags=[f"user:{user_id}", "invoice_settings"]
                )

            logger.debug(f"Cache warmed for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to warm cache for user {user_id}: {e}")


def warm_all_users_cache():
    """
    Warm cache for all active users.

    This should be called on application startup and periodically.
    """
    try:
        with get_db() as db:
            users = db.query(User).filter_by(is_active=True).all()
            logger.info(f"Warming cache for {len(users)} active users")

            for user in users:
                warm_user_cache(user.id)

            logger.info("Cache warming completed for all active users")
    except Exception as e:
        logger.error(f"Failed to warm cache for all users: {e}")


def warm_rate_limit_data():
    """
    Warm cache for rate limit data.

    Pre-loads common rate limit keys to reduce cache misses.
    """
    try:
        with get_db() as db:
            # Get active user IDs for rate limit warming
            users = db.query(User.id).filter_by(is_active=True).all()
            for (user_id,) in users:
                # Pre-warm rate limit keys
                cache_set(f"rate_limit:link:user:{user_id}:count", 0, ttl=300)
                cache_set(f"rate_limit:status:user:{user_id}:count", 0, ttl=300)

            logger.debug("Rate limit cache warming completed")
    except Exception as e:
        logger.warning(f"Failed to warm rate limit cache: {e}")


def warm_payment_summary_cache(user_id: int):
    """
    Warm payment summary cache for a user.

    Args:
        user_id: User ID to warm payment summary for
    """
    try:
        # This will be warmed by the payment_summary endpoint itself
        # We just trigger it by setting a placeholder
        cache_set(f"payment_summary:{user_id}", None, ttl=60)
        logger.debug(f"Payment summary cache warmed for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to warm payment summary cache for user {user_id}: {e}")
