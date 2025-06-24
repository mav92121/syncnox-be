from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, time, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from pydantic import BaseModel, Field, validator, conint, confloat
from pydantic.types import PositiveInt, conlist
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

class VehicleType(str, Enum):
    CAR = "car"
    TRUCK = "truck"
    BIKE = "bike"
    FOOT = "foot"
    VAN = "van"
    TRACTOR = "tractor"

class TimeWindow(BaseModel):
    start: time
    end: time
    
    def to_seconds(self, base_date: date = None) -> Tuple[int, int]:
        """Convert time window to seconds since midnight or from base_date if provided"""
        if base_date:
            start_dt = datetime.combine(base_date, self.start)
            end_dt = datetime.combine(base_date, self.end)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            return (
                int(start_dt.timestamp()),
                int(end_dt.timestamp())
            )
        return (
            self.start.hour * 3600 + self.start.minute * 60 + self.start.second,
            self.end.hour * 3600 + self.end.minute * 60 + self.end.second
        )

class VehicleBreak(BaseModel):
    """Represents a break that must be taken by a vehicle/driver"""
    id: str
    duration: PositiveInt = Field(..., description="Duration of the break in seconds")
    time_windows: List[TimeWindow] = Field(
        default_factory=list,
        description="Time windows when the break can be taken"
    )
    max_driving_duration_before: Optional[PositiveInt] = Field(
        None,
        description="Maximum driving duration before this break must be taken (in seconds)"
    )

class VehicleCosts(BaseModel):
    """Cost factors for a vehicle"""
    fixed: float = Field(0.0, ge=0, description="Fixed cost of using this vehicle")
    distance: float = Field(1.0, ge=0, description="Cost per meter")
    time: float = Field(0.0, ge=0, description="Cost per second")
    early: float = Field(0.0, ge=0, description="Cost per second early")
    late: float = Field(0.0, ge=0, description="Cost per second late")

class VehicleSkills(BaseModel):
    """Vehicle-specific skills/capabilities"""
    required_licenses: List[str] = Field(
        default_factory=list,
        description="Required licenses for this vehicle"
    )
    can_carry_hazardous: bool = False
    can_carry_refrigerated: bool = False
    max_weight: Optional[float] = Field(
        None, 
        ge=0, 
        description="Maximum weight capacity in kg"
    )
    max_volume: Optional[float] = Field(
        None, 
        ge=0, 
        description="Maximum volume capacity in cubic meters"
    )

class VehicleRequest(BaseModel):
    id: str
    type: VehicleType = VehicleType.CAR
    start_location: Location
    end_location: Optional[Location] = None
    time_window: Optional[TimeWindow] = None
    breaks: List[VehicleBreak] = Field(
        default_factory=list,
        description="List of breaks that must be taken by this vehicle"
    )
    costs: VehicleCosts = Field(
        default_factory=VehicleCosts,
        description="Cost factors for this vehicle"
    )
    skills: VehicleSkills = Field(
        default_factory=VehicleSkills,
        description="Skills and capabilities of this vehicle"
    )
    max_daily_driving_time: Optional[PositiveInt] = Field(
        None,
        description="Maximum daily driving time in seconds"
    )
    max_weekly_driving_time: Optional[PositiveInt] = Field(
        None,
        description="Maximum weekly driving time in seconds"
    )
    max_daily_distance: Optional[float] = Field(
        None,
        ge=0,
        description="Maximum daily driving distance in meters"
    )
    max_tasks: Optional[PositiveInt] = Field(
        None,
        description="Maximum number of tasks this vehicle can perform in a day"
    )
    speed_factor: float = Field(
        1.0,
        ge=0.1,
        le=2.0,
        description="Speed factor relative to normal speed (1.0 = normal speed)"
    )

class JobSkills(BaseModel):
    """Skills required by a job"""
    required_licenses: List[str] = Field(
        default_factory=list,
        description="Required licenses for this job"
    )
    requires_hazardous: bool = False
    requires_refrigeration: bool = False
    max_weight: Optional[float] = Field(
        None, 
        ge=0, 
        description="Weight of the item in kg"
    )
    volume: Optional[float] = Field(
        None, 
        ge=0, 
        description="Volume of the item in cubic meters"
    )

class JobRequest(BaseModel):
    id: str
    location: Location
    duration: int = Field(300, ge=0, description="Service duration in seconds")
    time_window: Optional[TimeWindow] = None
    priority: int = Field(1, ge=1, le=10, description="Priority from 1 (lowest) to 10 (highest)")
    required_skills: JobSkills = Field(
        default_factory=JobSkills,
        description="Skills required to perform this job"
    )
    allowed_vehicles: List[str] = Field(
        default_factory=list,
        description="List of vehicle IDs that can perform this job"
    )
    setup_duration: int = Field(
        0,
        ge=0,
        description="Additional setup time required before the job can start (in seconds)"
    )
    service_duration: int = Field(
        0,
        ge=0,
        description="Time required to perform the actual service (in seconds)"
    )
    pickup_delivery: Optional[Tuple[str, int]] = Field(
        None,
        description="For pickup and delivery jobs: (delivery_job_id, max_transit_time)"
    )

class PlanningHorizon(BaseModel):
    """Defines the time period for planning"""
    start_date: date
    end_date: date
    working_days: List[int] = Field(
        default_factory=lambda: list(range(5)),  # Monday to Friday by default
        description="List of weekday numbers (0=Monday, 6=Sunday) when the vehicle operates"
    )
    working_hours: Tuple[time, time] = Field(
        (time(9, 0), time(17, 0)),
        description="Working hours for each day (start_time, end_time)"
    )
    
    @validator('working_days', each_item=True)
    def validate_working_days(cls, v):
        if v < 0 or v > 6:
            raise ValueError("Working day must be between 0 (Monday) and 6 (Sunday)")
        return v

class OptimizationRequest(BaseModel):
    vehicles: List[VehicleRequest]
    jobs: List[JobRequest]
    optimization_type: OptimizationType = OptimizationType.DURATION
    planning_horizon: Optional[PlanningHorizon] = Field(
        None,
        description="Planning horizon for multi-day planning"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional optimization options"
    )
    
    @validator('vehicles')
    def validate_vehicles(cls, v):
        if not v:
            raise ValueError("At least one vehicle must be provided")
        return v
    
    @validator('jobs')
    def validate_jobs(cls, v):
        if not v:
            raise ValueError("At least one job must be provided")
        return v

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
                ),
                breaks=v.breaks,
                costs=v.costs,
                skills=v.skills,
                max_daily_driving_time=v.max_daily_driving_time,
                max_weekly_driving_time=v.max_weekly_driving_time,
                max_daily_distance=v.max_daily_distance,
                max_tasks=v.max_tasks,
                speed_factor=v.speed_factor
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
                priority=j.priority,
                required_skills=j.required_skills,
                allowed_vehicles=j.allowed_vehicles,
                setup_duration=j.setup_duration,
                service_duration=j.service_duration,
                pickup_delivery=j.pickup_delivery
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
            planning_horizon=request.planning_horizon,
            options=request.options
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
