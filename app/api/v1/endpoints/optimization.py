from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time, timedelta
from pydantic import BaseModel, Field, validator
from enum import Enum
from sqlalchemy.orm import Session
from app.services.route_optimizer import RouteOptimizer, RouteOptimizationError, Job, Vehicle
from app.api import deps
import logging

# Request/Response Models
class OptimizationType(str, Enum):
    DISTANCE = "distance"
    DURATION = "duration"

class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lng: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")

class TimeWindow(BaseModel):
    start: time
    end: time

class JobRequest(BaseModel):
    id: str
    location: Location
    duration: int = Field(300, ge=0, description="Service duration in seconds")
    time_window: Optional[TimeWindow] = None
    priority: int = Field(1, ge=1, le=10, description="Priority from 1 (lowest) to 10 (highest)")

class VehicleRequest(BaseModel):
    id: str
    start_location: Location
    end_location: Optional[Location] = None
    time_window: Optional[TimeWindow] = None

class OptimizationRequest(BaseModel):
    vehicles: List[VehicleRequest]
    jobs: List[JobRequest]
    optimization_type: OptimizationType = OptimizationType.DURATION
    options: Dict[str, Any] = {}

class Stop(BaseModel):
    job_id: str
    location: Location
    arrival_time: str
    departure_time: str
    distance_from_prev: float
    duration_from_prev: float
    service_time: int

class Route(BaseModel):
    vehicle_id: str
    stops: List[Stop]
    total_distance: float
    total_duration: float
    start_time: str
    end_time: str

class OptimizationResponse(BaseModel):
    status: str
    optimization_type: OptimizationType
    total_distance: float
    total_duration: float
    routes: List[Route]
    metadata: Dict[str, Any] = {}

# Error responses
class ErrorResponse(BaseModel):
    detail: str

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post(
    "/optimize",
    response_model=OptimizationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def optimize_routes(
    request: OptimizationRequest,
    db: Session = Depends(deps.get_db),
):
    """
    Optimize routes for the given vehicles and jobs.
    
    This endpoint will:
    1. Validate the input data
    2. Call the route optimization service
    3. Return the optimized routes with ETAs and distance information
    """
    try:
        logger.info(f"Starting route optimization for {len(request.jobs)} jobs and {len(request.vehicles)} vehicles")
        
        # Convert request models to service models
        vehicles = [
            Vehicle(
                id=v.id,
                start_location=(v.start_location.lat, v.start_location.lng),
                capacity=1,  # Default capacity
                time_window=(
                    (datetime.combine(datetime.today(), v.time_window.start).time(),
                     datetime.combine(datetime.today(), v.time_window.end).time())
                    if v.time_window else None
                )
            )
            for v in request.vehicles
        ]
        
        jobs = [
            Job(
                job_id=j.id,
                location=(j.location.lat, j.location.lng),
                duration=j.duration,
                time_window=(
                    (datetime.combine(datetime.today(), j.time_window.start),
                     datetime.combine(datetime.today(), j.time_window.end))
                    if j.time_window else None
                ),
                priority=j.priority
            )
            for j in request.jobs
        ]
        
        # Initialize the optimizer
        optimizer = RouteOptimizer()
        
        # Call the optimization service
        result = await optimizer.optimize_routes(
            vehicles=vehicles,
            jobs=jobs,
            optimization_type=request.optimization_type,
            **request.options
        )
        
        # Format the response
        response = {
            "status": "success",
            "optimization_type": request.optimization_type,
            "total_distance": result.get("total_distance", 0),
            "total_duration": result.get("total_duration", 0),
            "routes": [],
            "metadata": {
                "num_jobs": len(jobs),
                "num_vehicles": len(vehicles),
                "optimization_timestamp": result.get("optimization_timestamp")
            }
        }
        
        # Convert routes to the response format
        for route in result.get("routes", []):
            route_data = {
                "vehicle_id": route["vehicle_id"],
                "stops": [],
                "total_distance": route.get("total_distance", 0),
                "total_duration": route.get("total_duration", 0),
                "start_time": _format_timestamp(route.get("start_time")),
                "end_time": _format_timestamp(route.get("end_time"))
            }
            
            # Add stops to the route
            for stop in route.get("stops", []):
                route_data["stops"].append({
                    "job_id": stop["job_id"],
                    "location": {
                        "lat": stop["location"][0],
                        "lng": stop["location"][1]
                    },
                    "arrival_time": _format_timestamp(stop["arrival_time"]),
                    "departure_time": _format_timestamp(stop["departure_time"]),
                    "distance_from_prev": stop["distance_from_prev"],
                    "duration_from_prev": stop["duration_from_prev"],
                    "service_time": stop["service_time"]
                })
            
            response["routes"].append(route_data)
        
        return response
        
    except RouteOptimizationError as e:
        logger.error(f"Route optimization error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Route optimization failed: {str(e)}"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in route optimization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": f"An unexpected error occurred during route optimization: {str(e)}"}
        )
        
def _format_timestamp(timestamp: Any) -> str:
    """Format a timestamp to ISO format string"""
    if timestamp is None:
        return ""
    if isinstance(timestamp, (int, float)):
        # Convert seconds since midnight to time string
        hours = int(timestamp // 3600)
        minutes = int((timestamp % 3600) // 60)
        seconds = int(timestamp % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if hasattr(timestamp, 'isoformat'):
        return timestamp.isoformat()
    return str(timestamp)

@router.get("/status/{job_id}")
async def get_optimization_status(
    job_id: str,
):
    """
    Get the status of a route optimization job.
    """
    try:
        # In a real implementation, you would check the status from your optimization service
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error getting optimization status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
