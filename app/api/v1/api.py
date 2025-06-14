from fastapi import APIRouter

from app.api.v1.endpoints import jobs, optimization, drivers, vehicles

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(jobs.router)
api_router.include_router(optimization.router)
api_router.include_router(drivers.router)
api_router.include_router(vehicles.router)
