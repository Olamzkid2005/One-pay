"""
OnePay — DB-backed rate limiter with in-memory fallback.

Replaces the in-memory defaultdict so limits:
  - survive app restarts
  - work correctly across multiple gunicorn worker processes
  - fallback to memory cache on DB errors

Usage:
    from services.rate_limiter import check_rate_limit

    allowed = check_rate_limit(db, key="login:1.2.3.4", limit=5, window_secs=60)
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from models.rate_limit import RateLimit

logger = logging.getLogger(__name__)

# In-memory fallback cache for when DB is unavailable
_memory_cache = {}
_cache_lock = threading.Lock()
_cache_cleanup_last = time.time()


def check_rate_limit(db, key: str, limit: int, window_secs: int = 60, critical: bool = False) -> bool:
    """
    Return True if the request is allowed, False if rate-limited.

    Uses a fixed-window counter stored in the DB with in-memory fallback.
    The window resets every `window_secs` seconds.

    Args:
        db:          SQLAlchemy session (already open)
        key:         Unique string identifying the bucket, e.g. "login:1.2.3.4"
                     Max 255 chars, sanitized to prevent injection
        limit:       Max requests allowed in the window
        window_secs: Window duration in seconds. Note: because this uses a
                     fixed window (not sliding), up to 2× `limit` requests
                     can burst across a window boundary — e.g. `limit` at the
                     end of one window and `limit` at the start of the next.
        critical:    If True, fail closed (deny) on DB errors. If False, use
                     in-memory fallback and fail open.
    """
    # Sanitize key to prevent SQL injection and enforce length limit
    if not key or not isinstance(key, str):
        logger.warning("Invalid rate limit key type: %s", type(key))
        return True  # fail open
    
    # Validate key format
    import re
    if not re.match(r'^[a-zA-Z0-9:._-]{1,255}$', key):
        logger.warning("Invalid rate limit key format: %s", key[:50])
        return True  # fail open
    
    # Truncate and remove any null bytes
    key = key[:255].replace('\x00', '')
    
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_secs)

    try:
        record = (
            db.query(RateLimit)
            .filter(
                RateLimit.key == key,
                RateLimit.window_start >= window_start,
            )
            .first()
        )

        if record is None:
            # First request in this window
            record = RateLimit(key=key, window_start=now, count=1)
            db.add(record)
            db.flush()
            return True

        if record.count >= limit:
            logger.warning("Rate limit exceeded | key=%s count=%d limit=%d", key, record.count, limit)
            return False

        record.count += 1
        db.flush()
        return True

    except Exception as e:
        logger.error("Rate limiter DB error: %s", e)
        
        # For critical endpoints, fail closed (deny request)
        if critical:
            logger.warning("Rate limiter failing closed for critical endpoint | key=%s", key)
            return False
        
        # For non-critical endpoints, use in-memory fallback
        return _check_rate_limit_memory(key, limit, window_secs)


def _check_rate_limit_memory(key: str, limit: int, window_secs: int) -> bool:
    """
    In-memory fallback rate limiter when DB is unavailable.
    Uses thread-safe dictionary with periodic cleanup.
    """
    global _cache_cleanup_last
    
    with _cache_lock:
        now = time.time()
        
        # Periodic cleanup of old entries (every 5 minutes)
        if now - _cache_cleanup_last > 300:
            _cleanup_memory_cache(now)
            _cache_cleanup_last = now
        
        # Check if key exists in cache
        if key not in _memory_cache:
            _memory_cache[key] = {"count": 1, "window_start": now}
            logger.info("Rate limit (memory fallback) | key=%s count=1/%d", key, limit)
            return True
        
        cache_entry = _memory_cache[key]
        
        # Check if window has expired
        if now - cache_entry["window_start"] > window_secs:
            cache_entry["count"] = 1
            cache_entry["window_start"] = now
            logger.info("Rate limit (memory fallback) | key=%s count=1/%d (new window)", key, limit)
            return True
        
        # Check if limit exceeded
        if cache_entry["count"] >= limit:
            logger.warning("Rate limit exceeded (memory fallback) | key=%s count=%d limit=%d", 
                          key, cache_entry["count"], limit)
            return False
        
        # Increment counter
        cache_entry["count"] += 1
        return True


def _cleanup_memory_cache(now: float):
    """Remove expired entries from memory cache. Must be called with _cache_lock held."""
    expired_keys = [
        key for key, entry in _memory_cache.items()
        if now - entry["window_start"] > 7200  # 2 hours
    ]
    for key in expired_keys:
        del _memory_cache[key]
    if expired_keys:
        logger.info("Cleaned up %d expired memory cache entries", len(expired_keys))


def cleanup_old_rate_limits(db, older_than_secs: int = 3600):
    """
    Delete rate limit records older than `older_than_secs`.
    Call this periodically (e.g. from a scheduled task or health check)
    to prevent the table from growing unbounded.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_secs)
    deleted = db.query(RateLimit).filter(RateLimit.window_start < cutoff).delete()
    if deleted:
        logger.info("Cleaned up %d stale rate limit records", deleted)
    return deleted
