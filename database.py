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

from sqlalchemy import create_engine, event as _sa_event
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
    # Postgres / MySQL — sensible pool defaults
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
    _engine_kwargs["pool_pre_ping"] = True   # detect stale connections
    _engine_kwargs["pool_recycle"] = 3600    # recycle connections after 1 hour
    _engine_kwargs["pool_timeout"] = 30      # wait max 30s for connection

engine = create_engine(Config.DATABASE_URL, **_engine_kwargs)

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

    Example:
        with get_db() as db:
            db.add(obj)
            # auto-committed here
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_db_initialised = False

def init_db():
    """Create all tables. Called once at app startup — safe to call multiple times."""
    global _db_initialised
    if _db_initialised:
        return
    import models  # noqa: F401 — registers all models against Base
    from models.base import Base
    Base.metadata.create_all(bind=engine)
    _db_initialised = True
    logger.info("Database initialised")
