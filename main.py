import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.db.base import Base
from app.db.session import engine
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.cache import init_redis, close_redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Startup
    logger.info("Starting application...")
    
    # Initialize Redis if enabled
    if settings.ENABLE_REDIS:
        try:
            await init_redis()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)}")
            if settings.DEBUG:
                logger.warning("Running without Redis - some features may be limited")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Close Redis connection
    if settings.ENABLE_REDIS:
        await close_redis()
        logger.info("Redis connection closed")

# Create FastAPI app with lifespan events
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG
    }
