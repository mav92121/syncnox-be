from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "SyncNox"
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str
    DEBUG: bool

    class Config:
        env_file = ".env"

settings = Settings()
