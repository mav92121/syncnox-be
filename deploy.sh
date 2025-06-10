#!/bin/bash
set -e

echo "Starting deployment script..."

# Run database migrations
echo "Running database migrations..."

# Check if alembic_version exists
if ! psql $DATABASE_URL -c "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version'" | grep -q "(1 row)"; then
  echo "Initializing alembic migrations..."
  # Get the latest migration revision
  LATEST_REVISION=$(alembic heads | awk '{print $1}')
  echo "Setting current version to: $LATEST_REVISION"
  alembic stamp $LATEST_REVISION
fi

# Run migrations
alembic upgrade head
echo "Migrations completed successfully!"

# Start the application
echo "Starting the application..."
exec gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT main:app
