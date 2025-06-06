from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "SyncNox"
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str
    DEBUG: bool
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8000"]  # Add your frontend URLs

    class Config:
        env_file = ".env"

settings = Settings()
