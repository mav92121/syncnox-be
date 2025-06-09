#!/bin/bash
set -e

echo "Starting deployment script..."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head
echo "Migrations completed successfully!"

# Start the application
echo "Starting the application..."
exec gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT main:app
