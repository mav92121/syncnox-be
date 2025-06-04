from fastapi import FastAPI
from app.db.base import Base
from app.db.session import engine
from app.core.config import settings
from app.api.endpoints import jobs

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG
)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
