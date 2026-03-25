#!/bin/bash
set -e

echo "Running database migrations..."
python -m alembic upgrade head

echo "Starting application..."
exec gunicorn app:app \
  --bind 0.0.0.0:5000 \
  --workers 4 \
  --threads 2 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
