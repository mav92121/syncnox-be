from pydantic_settings import BaseSettings
from typing import List, Optional
from datetime import time

class Settings(BaseSettings):
    # Application metadata
    PROJECT_NAME: str = "SyncNox"
    PROJECT_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    # Database settings
    DATABASE_URL: str
    
    # CORS settings
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000"
    
    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_SOCKET_TIMEOUT: int = 5  # seconds
    REDIS_CONNECT_TIMEOUT: int = 5  # seconds
    REDIS_RETRY_ON_TIMEOUT: bool = True
    
    # Feature flags
    ENABLE_REDIS: bool = True
    ENABLE_CACHING: bool = True
    
    # GraphHopper API Settings
    GRAPHHOPPER_API_KEY: str
    GRAPHHOPPER_BASE_URL: str = "https://graphhopper.com/api/1/"
    GRAPHHOPPER_OPTIMIZE_ENDPOINT: str = "vrp/optimize"
    GRAPHHOPPER_SOLUTION_ENDPOINT: str = "vrp/solution/"
    
    # Default optimization parameters
    DEFAULT_VEHICLE_TYPE: str = "car"
    DEFAULT_OPTIMIZATION_TIMEOUT: int = 30  # seconds
    MAX_OPTIMIZATION_ATTEMPTS: int = 3
    
    # Default working hours (9 AM to 5 PM)
    DEFAULT_WORKING_HOURS_START: time = time(9, 0)
    DEFAULT_WORKING_HOURS_END: time = time(17, 0)
    
    # Default vehicle constraints
    DEFAULT_VEHICLE_CAPACITY: int = 1000  # kg
    DEFAULT_VEHICLE_VOLUME: int = 1000  # L
    DEFAULT_MAX_DRIVING_TIME: int = 8 * 3600  # 8 hours in seconds
    DEFAULT_MAX_DRIVING_DISTANCE: int = 500000  # 500 km in meters
    
    # Cache settings
    CACHE_TTL: int = 3600  # 1 hour in seconds
    MATRIX_CACHE_TTL: int = 86400  # 24 hours in seconds
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the CORS origins string into a list."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]
    
    @property
    def redis_config(self) -> dict:
        """Get Redis configuration as a dictionary."""
        return {
            "url": self.REDIS_URL,
            "password": self.REDIS_PASSWORD,
            "db": self.REDIS_DB,
            "socket_timeout": self.REDIS_SOCKET_TIMEOUT,
            "socket_connect_timeout": self.REDIS_CONNECT_TIMEOUT,
            "retry_on_timeout": self.REDIS_RETRY_ON_TIMEOUT,
        }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env files

settings = Settings()
