#!/bin/sh
set -e

echo "Starting application deployment..."

# Check if alembic_version exists
if psql $DATABASE_URL -c "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version'" | grep -q "(1 row)"; then
  echo "Alembic is initialized, running migrations..."
  alembic upgrade head
else
  echo "Initializing alembic migrations..."
  
  # Directly initialize with head revision
  echo "Stamping database with head revision"
  alembic stamp head
  
  echo "Alembic initialized with head revision"
fi

echo "Database is up to date!"

# Start the application
echo "Starting application server..."
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120
