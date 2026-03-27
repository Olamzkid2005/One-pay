"""
OnePay — Database migration script.
Adds new columns to existing tables without destroying data.
Safe to run multiple times (checks before adding).

Supports both SQLite and PostgreSQL.

⚠️  DEPRECATION NOTICE:
This script is deprecated in favor of Alembic migrations.
For new installations, use: alembic upgrade head
This script remains for backward compatibility with existing deployments.

Usage:
    python migrate.py
    DATABASE_URL=postgresql://user:pass@host/db python migrate.py
"""
import os
import sys
import warnings
from dotenv import load_dotenv

load_dotenv()

warnings.warn(
    "migrate.py is deprecated. Use 'alembic upgrade head' for new installations.",
    DeprecationWarning,
    stacklevel=2
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///onepay.db")
IS_POSTGRES = "postgresql" in DATABASE_URL

# (table, column, definition)
MIGRATIONS = [
    # users — new columns added in refactor
    ("users", "email",                    "VARCHAR(255)"),
    ("users", "webhook_url",              "VARCHAR(500)"),
    ("users", "failed_login_attempts",    "INTEGER DEFAULT 0"),
    ("users", "locked_until",             "TIMESTAMP"),
    ("users", "reset_token",              "VARCHAR(255)"),
    ("users", "reset_token_expires_at",   "TIMESTAMP"),

    # transactions — new columns added in refactor
    ("transactions", "idempotency_key",       "VARCHAR(255)"),
    ("transactions", "webhook_url",           "VARCHAR(500)"),
    ("transactions", "webhook_delivered",     "BOOLEAN DEFAULT FALSE"),
    ("transactions", "webhook_delivered_at",  "TIMESTAMP"),
    ("transactions", "webhook_attempts",      "INTEGER DEFAULT 0"),
    ("transactions", "webhook_last_error",    "TEXT"),
    ("transactions", "qr_code_payment_url",    "TEXT"),
    ("transactions", "qr_code_virtual_account", "TEXT"),
]


def get_existing_columns_sqlite(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def get_existing_columns_postgres(cur, table):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    return {row[0] for row in cur.fetchall()}


def run_sqlite():
    import sqlite3
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    applied = 0
    skipped = 0

    for table, column, definition in MIGRATIONS:
        existing = get_existing_columns_sqlite(cur, table)
        if column in existing:
            print(f"  skip  {table}.{column} (already exists)")
            skipped += 1
            continue

        sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        cur.execute(sql)
        print(f"  added {table}.{column}")
        applied += 1

    # Create rate_limits table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            key          VARCHAR(255) NOT NULL,
            window_start TIMESTAMP NOT NULL,
            count        INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_rate_limits_key_window ON rate_limits (key, window_start)"
    )
    print("  ok    rate_limits table")

    # Add index for idempotency_key if not present
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_transactions_idempotency_key
        ON transactions (idempotency_key)
        WHERE idempotency_key IS NOT NULL
    """)
    print("  ok    transactions.idempotency_key index")

    conn.commit()
    conn.close()

    print(f"\nDone — {applied} column(s) added, {skipped} skipped.")


def run_postgres():
    import psycopg2
    from urllib.parse import urlparse
    
    parsed = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip("/"),
    )
    cur = conn.cursor()

    applied = 0
    skipped = 0

    for table, column, definition in MIGRATIONS:
        existing = get_existing_columns_postgres(cur, table)
        if column in existing:
            print(f"  skip  {table}.{column} (already exists)")
            skipped += 1
            continue

        # PostgreSQL supports IF NOT EXISTS in ALTER TABLE ADD COLUMN (9.6+)
        sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"
        cur.execute(sql)
        print(f"  added {table}.{column}")
        applied += 1

    # Create rate_limits table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id           SERIAL PRIMARY KEY,
            key          VARCHAR(255) NOT NULL,
            window_start TIMESTAMP NOT NULL,
            count        INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_rate_limits_key_window ON rate_limits (key, window_start)"
    )
    print("  ok    rate_limits table")

    # Add index for idempotency_key if not present
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_transactions_idempotency_key
        ON transactions (idempotency_key)
        WHERE idempotency_key IS NOT NULL
    """)
    print("  ok    transactions.idempotency_key index")

    conn.commit()
    conn.close()

    print(f"\nDone — {applied} column(s) added, {skipped} skipped.")


if __name__ == "__main__":
    print(f"Migrating {DATABASE_URL}...\n")
    if IS_POSTGRES:
        run_postgres()
    else:
        run_sqlite()
