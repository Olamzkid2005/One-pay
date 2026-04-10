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
import re
import threading
import time
from datetime import datetime, timedelta, timezone

from models.rate_limit import RateLimit

logger = logging.getLogger(__name__)

# In-memory fallback cache for when DB is unavailable
_memory_cache = {}
_cache_lock = threading.Lock()
_cache_cleanup_last = time.time()

# Pre-compile regex at module level to prevent ReDoS (VULN-016)
_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9:._-]{1,255}$')


def _validate_rate_limit_key(key: str) -> bool:
    """Return True if key is valid for rate limiting, False otherwise."""
    if not key or not isinstance(key, str):
        logger.warning("Invalid rate limit key type: %s", type(key))
        return False
    if len(key) > 255:
        logger.warning("Rate limit key too long: %d chars", len(key))
        return False
    if not _KEY_PATTERN.match(key):
        logger.warning("Invalid rate limit key format: %s", key[:50])
        return False
    return True


def check_rate_limit(db, key: str, limit: int, window_secs: int = 60, critical: bool = False) -> bool:
    """
    Return True if the request is allowed, False if rate-limited.
    Uses a fixed-window counter stored in the DB with in-memory fallback.
    """
    if not _validate_rate_limit_key(key):
        return True  # fail open on invalid key

    key = key.replace('\x00', '')
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_secs)

    try:
        with db.begin_nested():
            record = (
                db.query(RateLimit)
                .filter(RateLimit.key == key, RateLimit.window_start >= window_start)
                .with_for_update()
                .first()
            )
            if record is None:
                db.add(RateLimit(key=key, window_start=now, count=1))
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
        if critical:
            logger.warning("Rate limiter failing closed for critical endpoint | key=%s", key)
            return False
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
