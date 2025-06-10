#!/bin/sh
set -e

echo "Starting application deployment..."

echo "Downgrading to previous revision..."
alembic downgrade -1
echo "Downgraded successfully!"

# Check if alembic_version table exists
if psql $DATABASE_URL -tAc "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version');" | grep -q "t"; then
  echo "Alembic is initialized, running migrations..."
  alembic upgrade head
else
  echo "Initializing alembic migrations..."
  
  echo "Stamping database with head revision"
  alembic stamp head
  
  echo "Alembic initialized with head revision"
fi

echo "Database is up to date!"
echo "Current Alembic revision:"
alembic current || echo "No current revision"

echo "Starting application server..."
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120
