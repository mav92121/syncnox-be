#!/bin/sh
# Entrypoint for running Gunicorn with Uvicorn workers

# Run database migrations here if needed, e.g.:
alembic upgrade head

exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
