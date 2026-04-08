# Database Operations Skill

Manage database schema, migrations, and data.

## When to Use
- User wants to check database state
- Running migrations
- Inspecting data
- Adding new models

## Database Info
- Dev: SQLite (`onepay.db`)
- Prod: PostgreSQL (via docker-compose)
- ORM: SQLAlchemy 2.x

## Common Tasks

### Check Migration Status
```bash
alembic current
alembic history
```

### Run Migrations
```bash
alembic upgrade head
```

### Rollback
```bash
alembic downgrade -1
```

### Create New Migration
```bash
alembic revision --autogenerate -m "add column to users"
```

### Inspect Data (Python)
```python
from database import Session
from models.user import User
session = Session()
users = session.query(User).all()
```

## Key Files
- `alembic/env.py` - Migration configuration
- `alembic/versions/` - Migration scripts
- `models/` - SQLAlchemy models
- `database.py` - Engine and session setup
