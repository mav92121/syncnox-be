from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "SyncNox"
    DATABASE_URL: str
    ENVIRONMENT: str
    DEBUG: bool
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    # CORS settings
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the CORS origins string into a list."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]
    
    # GraphHopper API Settings
    GRAPHHOPPER_API_KEY: str
    GRAPHHOPPER_BASE_URL: str = "https://graphhopper.com/api/1/"
    GRAPHHOPPER_OPTIMIZE_ENDPOINT: str = "vrp/optimize"
    GRAPHHOPPER_SOLUTION_ENDPOINT: str = "vrp/solution/"
    
    # Default optimization parameters
    DEFAULT_VEHICLE_TYPE: str = "car"
    DEFAULT_OPTIMIZATION_TIMEOUT: int = 60  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
