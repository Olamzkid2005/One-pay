# Database Migration

Check the current database migration status and run any pending migrations:

```bash
cd /Users/mac/Documents/One-pay && alembic current && alembic history
```

If there are pending migrations, run them:

```bash
cd /Users/mac/Documents/One-pay && alembic upgrade head
```

Report:
- Current migration version
- Number of pending migrations
- Any migration errors

To create a new migration after model changes:
```bash
alembic revision --autogenerate -m "description"
```
