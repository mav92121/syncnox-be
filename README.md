# Syncnox Route Optimization Backend

This is a scalable, production-ready FastAPI backend for a B2B route optimization SaaS

## Features

- Modular FastAPI architecture (versioned API, service layers)
- Dockerized for easy deployment
- PostgreSQL support
- Production-ready with Gunicorn & Uvicorn workers
- Auto-deploy via GitHub Actions and Render

## Getting Started

### 1. Local Development

1. **Clone the repository:**
   ```sh
   git clone <your-repo-url>
   cd syncnox-be
   ```
2. **Create and activate a virtual environment:**
   ```sh
   python -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Configure environment variables:**
   - Copy `.env.example` to `.env` and fill in values (see below).
5. **Run the app:**
   ```sh
   uvicorn main:app --reload
   ```

### 2. Production Deployment (Render)

- Dockerfile included for containerized deployments.
- Auto-deploy on push via GitHub Actions.
- Set environment variables (e.g., `DATABASE_URL`, `SECRET_KEY`) in Render dashboard.
- Uses Gunicorn with Uvicorn workers for production.

## Environment Variables

| Key          | Description                   |
| ------------ | ----------------------------- |
| DATABASE_URL | PostgreSQL connection string  |
| SECRET_KEY   | Your app secret key           |
| ENVIRONMENT  | `development` or `production` |
| DEBUG        | `True` or `False`             |

## API Documentation

- Interactive docs available at `/docs` when running.
