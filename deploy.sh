#!/bin/bash
set -e

echo "Running migration fix..."

alembic upgrade head

echo "Fix complete — launching app..."
exec gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT main:app
