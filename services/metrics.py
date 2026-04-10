"""
OnePay — Prometheus Metrics Service
Centralized metrics tracking for business logic and operations.
"""

import logging
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge

    # Transaction metrics
    transaction_counter = Counter(
        'transactions_total',
        'Total number of transactions',
        ['status', 'currency']
    )

    transaction_duration = Histogram(
        'transaction_duration_seconds',
        'Transaction processing duration'
    )

    # User metrics
    active_users = Gauge(
        'active_users',
        'Number of active users'
    )

    # API request metrics
    api_request_counter = Counter(
        'api_requests_total',
        'Total number of API requests',
        ['endpoint', 'method', 'status']
    )

    api_request_duration = Histogram(
        'api_request_duration_seconds',
        'API request processing duration',
        ['endpoint']
    )

    # Cache metrics
    cache_hits = Counter(
        'cache_hits_total',
        'Total number of cache hits',
        ['cache_type']
    )

    cache_misses = Counter(
        'cache_misses_total',
        'Total number of cache misses',
        ['cache_type']
    )

    # Webhook metrics
    webhook_deliveries = Counter(
        'webhook_deliveries_total',
        'Total number of webhook deliveries',
        ['status']
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not installed - metrics disabled")
    PROMETHEUS_AVAILABLE = False

    # Create no-op stubs
    class Counter:
        def __init__(self, *args, **kwargs):
            self.labels = lambda *args, **kwargs: self
            def inc(self, amount=1): pass
            self.inc = inc

    class Histogram:
        def __init__(self, *args, **kwargs):
            self.labels = lambda *args, **kwargs: self
            def observe(self, amount): pass
            self.observe = observe
            def time(self): return lambda f: f
            self.time = time

    class Gauge:
        def __init__(self, *args, **kwargs):
            def set(self, value): pass
            self.set = set
            def inc(self, amount=1): pass
            self.inc = inc
            def dec(self, amount=1): pass
            self.dec = dec

    # Create stub instances
    transaction_counter = Counter()
    transaction_duration = Histogram()
    active_users = Gauge()
    api_request_counter = Counter()
    api_request_duration = Histogram()
    cache_hits = Counter()
    cache_misses = Counter()
    webhook_deliveries = Counter()


def track_transaction(status: str, currency: str):
    """Track a transaction event."""
    if PROMETHEUS_AVAILABLE:
        transaction_counter.labels(status=status, currency=currency).inc()


def track_transaction_duration(duration: float):
    """Track transaction processing duration."""
    if PROMETHEUS_AVAILABLE:
        transaction_duration.observe(duration)


def track_api_request(endpoint: str, method: str, status: int, duration: float):
    """Track an API request."""
    if PROMETHEUS_AVAILABLE:
        api_request_counter.labels(endpoint=endpoint, method=method, status=status).inc()
        api_request_duration.labels(endpoint=endpoint).observe(duration)


def track_cache_hit(cache_type: str):
    """Track a cache hit."""
    if PROMETHEUS_AVAILABLE:
        cache_hits.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str):
    """Track a cache miss."""
    if PROMETHEUS_AVAILABLE:
        cache_misses.labels(cache_type=cache_type).inc()


def track_webhook_delivery(status: str):
    """Track a webhook delivery."""
    if PROMETHEUS_AVAILABLE:
        webhook_deliveries.labels(status=status).inc()


def update_active_users(count: int):
    """Update the active users gauge."""
    if PROMETHEUS_AVAILABLE:
        active_users.set(count)


def timed_transaction(func: Callable) -> Callable:
    """Decorator to track transaction duration."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            track_transaction_duration(duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            track_transaction_duration(duration)
            raise
    return wrapper


def timed_api_request(endpoint: str, method: str) -> Callable:
    """Decorator to track API request duration."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 500
            try:
                result = func(*args, **kwargs)
                # Try to get status from response if it's a Flask response
                if hasattr(result, 'status_code'):
                    status = result.status_code
                else:
                    status = 200
                duration = time.time() - start_time
                track_api_request(endpoint, method, status, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                track_api_request(endpoint, method, status, duration)
                raise
        return wrapper
    return decorator
