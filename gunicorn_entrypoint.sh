#!/bin/sh
set -e

echo "Starting application deployment..."

# Check if alembic_version exists
if psql $DATABASE_URL -c "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version'" | grep -q "(1 row)"; then
  echo "Alembic is initialized, running migrations..."
  alembic upgrade head
else
  echo "Initializing alembic migrations..."
  # Get the latest migration revision
  LATEST_REVISION=$(alembic history | grep "^[a-f0-9]\+" | head -1 | cut -d ":" -f 1 | tr -d " ")
  echo "Setting current version to: $LATEST_REVISION"
  alembic stamp $LATEST_REVISION
fi

echo "Database is up to date!"

# Start the application
echo "Starting application server..."
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120
