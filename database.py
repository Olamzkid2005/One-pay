"""
OnePay — Database setup and session management.

Usage:
    from database import get_db

    with get_db() as db:
        user = db.query(User).first()
        # session auto-commits on clean exit, rolls back on exception
"""

import contextlib
import logging

from sqlalchemy import create_engine
from sqlalchemy import event as _sa_event
from sqlalchemy.orm import sessionmaker

from config import Config

logger = logging.getLogger(__name__)

# ── Engine ─────────────────────────────────────────────────────────────────────

_engine_kwargs = {}

if "sqlite" in Config.DATABASE_URL:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    # SQLite-specific: limit connections to prevent lock contention
    _engine_kwargs["pool_size"] = 5
    # Note: max_overflow not supported with SQLite's SingletonThreadPool
else:
    # Postgres / MySQL — use configurable pool settings
    _engine_kwargs["pool_size"] = Config.DB_POOL_SIZE
    _engine_kwargs["max_overflow"] = Config.DB_MAX_OVERFLOW
    _engine_kwargs["pool_pre_ping"] = Config.DB_POOL_PRE_PING
    _engine_kwargs["pool_recycle"] = Config.DB_POOL_RECYCLE
    _engine_kwargs["pool_timeout"] = Config.DB_POOL_TIMEOUT

engine = create_engine(Config.DATABASE_URL, **_engine_kwargs)

# Slow query logging for development
if Config.DEBUG or Config.SQLALCHEMY_ECHO:
    import time as _time

    @_sa_event.listens_for(engine, "before_cursor_execute")
    def _log_slow_query_before(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault('query_start_time', []).append(_time.time())

    @_sa_event.listens_for(engine, "after_cursor_execute")
    def _log_slow_query_after(conn, cursor, statement, parameters, context, executemany):
        total = _time.time() - conn.info['query_start_time'].pop(-1)
        if total > 0.1:  # Log queries slower than 100ms
            logger.warning(f"Slow query ({total:.2f}s): {statement[:200]}")

# Connection pool monitoring
if Config.DEBUG:
    @_sa_event.listens_for(engine, "connect")
    def on_connect(dbapi_conn, connection_record):
        pool = engine.pool
        checkedout = getattr(pool, 'checkedout', 0)
        logger.debug(f"New DB connection created. Pool size: {pool.size}, Checked out: {checkedout}")

    @_sa_event.listens_for(engine, "close")
    def on_close(dbapi_conn, connection_record):
        pool = engine.pool
        checkedout = getattr(pool, 'checkedout', 0)
        logger.debug(f"DB connection closed. Pool size: {pool.size}, Checked out: {checkedout}")

# SQLite pragmas: WAL mode + foreign keys
if "sqlite" in Config.DATABASE_URL:

    @_sa_event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextlib.contextmanager
def get_db():
    """
    Yield a database session as a context manager.

    - Commits on clean exit
    - Rolls back and re-raises on any exception
    - Always closes the session
    - Skips commit if session was already rolled back inside the block

    Example:
        with get_db() as db:
            db.add(obj)
            # auto-committed here
    """
    db = SessionLocal()
    try:
        yield db
        if db.in_transaction():
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_db_initialised = False


def init_db() -> None:
    """Create all tables. Called once at app startup — safe to call multiple times."""
    global _db_initialised
    if _db_initialised:
        return
    import models  # noqa: F401 — registers all models against Base
    from models.base import Base

    Base.metadata.create_all(bind=engine)
    _db_initialised = True
    logger.info("Database initialised")
