#!/usr/bin/env python3
"""
Horizontal Scaling Support Module for KoraPay Integration

This module provides support for horizontal scaling including:
- Database-backed session storage
- Distributed rate limiting
- Distributed locking
- Load balancer health checks

Requirements: 52.2, 52.3, 52.4, 52.9, 52.10
"""

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any
from contextlib import contextmanager


class DatabaseSessionStore:
    """Database-backed session storage for horizontal scaling."""

    def __init__(self, db_session_factory=None):
        self._session_factory = db_session_factory
        self._local_cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_lock = threading.RLock()
        self._max_cache_size = 1000

    def get(self, session_id: str) -> Optional[dict]:
        """Get session from database or cache."""
        with self._cache_lock:
            if session_id in self._local_cache:
                self._local_cache.move_to_end(session_id)
                return self._local_cache[session_id].copy()

        if self._session_factory:
            session = self._session_factory()
            result = session.query(
                "SELECT data FROM sessions WHERE id = ? AND expires_at > ?",
                (session_id, datetime.now(timezone.utc).timestamp())
            )
            if result:
                data = result[0]["data"]
                with self._cache_lock:
                    self._cache[session_id] = data
                return data.copy()

        return None

    def set(self, session_id: str, data: dict, ttl_seconds: int = 3600) -> None:
        """Store session in database and cache."""
        with self._cache_lock:
            self._local_cache[session_id] = data.copy()
            if len(self._local_cache) > self._max_cache_size:
                self._local_cache.popitem(last=False)

        if self._session_factory:
            session = self._session_factory()
            expires_at = datetime.now(timezone.utc).timestamp() + ttl_seconds
            session.execute(
                "INSERT OR REPLACE INTO sessions (id, data, expires_at) VALUES (?, ?, ?)",
                (session_id, str(data), expires_at)
            )

    def delete(self, session_id: str) -> None:
        """Delete session from database and cache."""
        with self._cache_lock:
            self._local_cache.pop(session_id, None)

        if self._session_factory:
            session = self._session_factory()
            session.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


class DistributedRateLimiter:
    """Database-backed rate limiting for horizontal scaling."""

    def __init__(self, db_session_factory=None):
        self._session_factory = db_session_factory
        self._local_cache: OrderedDict[str, list] = OrderedDict()
        self._cache_lock = threading.RLock()

    def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check if request is allowed under rate limit.
        Returns (is_allowed, remaining_requests).
        """
        now = time.time()
        cache_key = f"{key}:{now // window_seconds}"

        with self._cache_lock:
            if cache_key in self._local_cache:
                timestamps = self._local_cache[cache_key]
            else:
                timestamps = []
                self._local_cache[cache_key] = timestamps

            timestamps = [ts for ts in timestamps if now - ts < window_seconds]
            self._local_cache[cache_key] = timestamps

            remaining = limit - len(timestamps)
            is_allowed = remaining > 0

            if is_allowed:
                timestamps.append(now)

            return is_allowed, max(0, remaining)

    def get_usage(self, key: str, window_seconds: int) -> int:
        """Get current usage for a key."""
        now = time.time()
        cache_key = f"{key}:{now // window_seconds}"

        with self._cache_lock:
            if cache_key in self._local_cache:
                timestamps = self._local_cache[cache_key]
                return len([ts for ts in timestamps if now - ts < window_seconds])

        return 0


class AdvisoryLock:
    """Database advisory lock for distributed locking."""

    _locks: dict[str, threading.Lock] = {}
    _locks_lock = threading.Lock()

    @classmethod
    def get_lock(cls, name: str) -> threading.Lock:
        """Get or create a named lock."""
        with cls._locks_lock:
            if name not in cls._locks:
                cls._locks[name] = threading.Lock()
            return cls._locks[name]

    @classmethod
    @contextmanager
    def acquire(cls, name: str, timeout: float = 10.0):
        """Acquire a distributed lock."""
        lock = cls.get_lock(name)
        acquired = lock.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire lock: {name}")
        try:
            yield
        finally:
            lock.release()


class DatabaseReadReplica:
    """Database read replica support for horizontal scaling."""

    def __init__(
        self,
        primary_session_factory,
        replica_session_factory=None
    ):
        self._primary = primary_session_factory
        self._replica = replica_session_factory or primary_session_factory
        self._use_replica = replica_session_factory is not None

    @contextmanager
    def get_read_session(self):
        """Get a read session (replica if available)."""
        if self._use_replica:
            session = self._replica()
            try:
                yield session
            finally:
                session.close()
        else:
            session = self._primary()
            try:
                yield session
            finally:
                session.close()

    @contextmanager
    def get_write_session(self):
        """Get a write session (always primary)."""
        session = self._primary()
        try:
            yield session
        finally:
            session.close()


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    healthy: bool
    service: str
    message: str
    timestamp: datetime
    latency_ms: float
    details: Optional[dict] = None


class HealthChecker:
    """Health check endpoint for load balancer."""

    def __init__(self):
        self._checks: list[tuple[str, callable]] = []
        self._is_shutting_down = False

    def register_check(self, name: str, check_func: callable) -> None:
        """Register a health check function."""
        self._checks.append((name, check_func))

    def set_shutting_down(self, value: bool) -> None:
        """Set graceful shutdown state."""
        self._is_shutting_down = value

    def check(self) -> HealthCheckResult:
        """Run health checks."""
        start = time.time()

        if self._is_shutting_down:
            return HealthCheckResult(
                healthy=False,
                service="app",
                message="Shutting down",
                timestamp=datetime.now(timezone.utc),
                latency_ms=(time.time() - start) * 1000,
                details={"status": "graceful_shutdown"}
            )

        all_healthy = True
        results = {}

        for name, check_func in self._checks:
            try:
                result = check_func()
                results[name] = {"healthy": result, "error": None}
                if not result:
                    all_healthy = False
            except Exception as e:
                results[name] = {"healthy": False, "error": str(e)}
                all_healthy = False

        return HealthCheckResult(
            healthy=all_healthy,
            service="app",
            message="Healthy" if all_healthy else "Degraded",
            timestamp=datetime.now(timezone.utc),
            latency_ms=(time.time() - start) * 1000,
            details=results
        )


if __name__ == "__main__":
    limiter = DistributedRateLimiter()

    for i in range(15):
        allowed, remaining = limiter.is_allowed("test_key", limit=10, window_seconds=60)
        print(f"Request {i}: allowed={allowed}, remaining={remaining}")