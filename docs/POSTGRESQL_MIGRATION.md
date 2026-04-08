# SQLite to PostgreSQL Migration Guide

OnePay uses PostgreSQL in all environments (development, staging, production).
This guide covers how to get PostgreSQL running locally and common gotchas when
migrating from SQLite.

---

## Starting PostgreSQL via Docker Compose

The easiest way to run PostgreSQL locally is with the included `docker-compose.yml`.

```bash
# Start only the database (no need to run the full stack)
docker compose up db -d

# Verify it's healthy
docker compose ps db
```

The database will be available at `postgresql://onepay_user:onepay_pass@localhost:5432/onepay`.

Your `.env` should have:

```
DATABASE_URL=postgresql://onepay_user:onepay_pass@localhost:5432/onepay
```

Data is persisted in the `pgdata` Docker volume, so it survives container restarts.
To wipe the database and start fresh:

```bash
docker compose down -v   # removes volumes
docker compose up db -d
```

---

## Running Migrations

Once PostgreSQL is running, apply all Alembic migrations:

```bash
# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# View migration history
alembic history --verbose
```

If you're starting from scratch (no existing data), `alembic upgrade head` is all you need.

---

## Common Gotchas

### 1. `func.strftime` is SQLite-only

SQLite's `func.strftime("%Y-%m-%d", col)` does not exist in PostgreSQL.
Use `func.to_char(col, 'YYYY-MM-DD')` instead, or `func.date_trunc('day', col)` when
you only need to group by day without formatting.

**SQLite (broken on PostgreSQL):**
```python
func.strftime("%Y-%m-%d", Transaction.created_at).label("day")
```

**PostgreSQL-compatible:**
```python
func.to_char(Transaction.created_at, "YYYY-MM-DD").label("day")
```

The codebase detects the dialect at runtime and uses the correct function — see
`blueprints/payments.py` `payment_summary()`.

### 2. Timezone-aware datetimes

PostgreSQL's `TIMESTAMP WITH TIME ZONE` stores UTC and returns timezone-aware
`datetime` objects. SQLite stores naive datetimes (no timezone info).

All `DateTime` columns in the models use `DateTime(timezone=True)` and default to
`datetime.now(timezone.utc)`. The `Transaction._to_utc()` helper normalises any
naive datetimes that may come from legacy SQLite data.

**Always use timezone-aware datetimes when writing queries:**
```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)          # correct
now = datetime.utcnow()                   # wrong — naive datetime
```

### 3. JSON columns

PostgreSQL has a native `JSONB` type. SQLite stores JSON as plain `Text`.
SQLAlchemy's `JSON` type handles serialisation/deserialisation transparently for
both dialects, but there are subtle differences:

- PostgreSQL `JSONB` supports indexing and operators (`@>`, `?`, etc.)
- SQLite `Text`-backed JSON does not support those operators
- Avoid raw SQL JSON operators; use Python-level filtering instead

### 4. Case-sensitive `LIKE`

PostgreSQL `LIKE` is case-sensitive by default. SQLite `LIKE` is case-insensitive
for ASCII characters. Use `ILIKE` in PostgreSQL or `func.lower()` on both sides
for portable case-insensitive searches.

### 5. Boolean literals

SQLite accepts `1`/`0` as booleans. PostgreSQL requires `TRUE`/`FALSE`.
SQLAlchemy handles this automatically — never use raw `1`/`0` in ORM queries.

### 6. `AUTOINCREMENT` vs `SERIAL`

SQLite uses `AUTOINCREMENT`; PostgreSQL uses `SERIAL` / `BIGSERIAL` / `IDENTITY`.
SQLAlchemy's `Integer` primary key maps to the correct type per dialect — no
manual changes needed.

### 7. Connection pool settings

SQLite uses a single-thread pool. PostgreSQL uses a real connection pool.
`database.py` already configures appropriate pool settings per dialect:

- SQLite: `pool_size=5`, no `max_overflow`
- PostgreSQL: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`

### 8. `sqlite:///:memory:` in tests

The test config (`TestingConfig`) still uses `sqlite:///:memory:` for fast,
isolated unit tests. Integration tests that need PostgreSQL-specific behaviour
should set `DATABASE_URL` to a real PostgreSQL instance (e.g. via a test
docker-compose service).

---

## Verifying the Setup

```bash
# Connect to the running container
docker compose exec db psql -U onepay_user -d onepay

# List tables (should show all after migrations)
\dt

# Check a sample query
SELECT COUNT(*) FROM transactions;
```
