# Production-ready Dockerfile for FastAPI
FROM python:3.11-slim as base

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY ./app ./app
COPY ./main.py ./main.py

# Create non-root user
RUN useradd -m appuser
USER appuser

# Entrypoint for production
CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]
