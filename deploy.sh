#!/bin/bash
set -e

echo "Running migration fix..."

alembic downgrade -1
echo "Downgraded successfully!"
alembic upgrade head

echo "Fix complete — launching app..."
exec gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT main:app
