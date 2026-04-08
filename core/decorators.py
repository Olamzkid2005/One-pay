"""
OnePay — Reusable decorators for Flask routes.

Provides rate limiting, caching, and audit logging decorators.
"""
import logging
from functools import wraps
from flask import request, g, jsonify

from core.ip import client_ip
from database import get_db
from services.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)


def rate_limit(key: str, limit: int, window_secs: int = 60, critical: bool = False):
    """
    Decorator for rate limiting routes.

    Args:
        key: Rate limit key template. Supports {user_id}, {ip}, {api_key} placeholders.
              Example: "login:{ip}" or "api:{user_id}"
        limit: Maximum requests allowed in window
        window_secs: Window duration in seconds (default: 60)
        critical: If True, fail closed (deny) on DB errors. If False, fail open.

    Usage:
        @rate_limit("login:{ip}", limit=5, window_secs=60)
        def login():
            ...

        @rate_limit("api:{user_id}", limit=100, window_secs=60)
        def api_endpoint():
            ...
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Resolve key placeholders
            resolved_key = key.format(
                user_id=g.get("user_id", "anon"),
                ip=client_ip(),
                api_key=g.get("api_key", "none")
            )

            with get_db() as db:
                if not check_rate_limit(db, resolved_key, limit, window_secs, critical):
                    logger.warning(
                        "Rate limit exceeded | key=%s limit=%d window=%ds path=%s",
                        resolved_key, limit, window_secs, request.path
                    )
                    return jsonify({
                        "success": False,
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please wait and try again.",
                        "retry_after": window_secs
                    }), 429, {"Retry-After": str(window_secs)}

            return f(*args, **kwargs)

        return wrapped

    return decorator