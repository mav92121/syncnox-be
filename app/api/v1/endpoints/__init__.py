from fastapi import APIRouter

from app.api.v1.endpoints import jobs, optimization, drivers, vehicles

router = APIRouter()
router.include_router(jobs.router, tags=["jobs"])
router.include_router(optimization.router, tags=["optimization"])
router.include_router(drivers.router, tags=["drivers"])
router.include_router(vehicles.router, tags=["vehicles"])

