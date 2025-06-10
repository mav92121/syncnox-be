#!/bin/bash
set -e

echo "Starting deployment script..."

# Run database migrations
echo "Running database migrations..."

# Check if alembic_version exists
if ! psql $DATABASE_URL -c "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version'" | grep -q "(1 row)"; then
  echo "First-time DB init: stamping to current head..."
  alembic stamp head
fi
# Run migrations
alembic downgrade beed49420ecd
alembic upgrade head
echo "Migrations completed successfully!"

# Start the application
echo "Starting the application..."
exec gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT main:app
