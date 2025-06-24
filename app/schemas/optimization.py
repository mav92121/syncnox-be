from datetime import time, date, datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Union
from pydantic import BaseModel, Field, validator, model_validator
from pydantic.types import confloat, conint

# Type aliases
Location = Tuple[float, float]  # (latitude, longitude)

class VehicleType(str, Enum):
    """Types of vehicles supported for routing."""
    CAR = "car"
    TRUCK = "truck"
    BIKE = "bike"
    FOOT = "foot"
    SCOOTER = "scooter"
    MOTORCYCLE = "motorcycle"
    SMALL_TRUCK = "small_truck"
    LARGE_TRUCK = "large_truck"

class OptimizationType(str, Enum):
    """Types of optimization objectives."""
    DURATION = "duration"
    DISTANCE = "distance"
    COST = "cost"
    COMBINED = "combined"


class OptimizationStatus(str, Enum):
    """Status of an optimization operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TimeWindow(BaseModel):
    """Time window with start and end times in seconds since midnight."""
    start: int = Field(..., ge=0, le=86400, description="Start time in seconds since midnight")
    end: int = Field(..., ge=0, le=86400, description="End time in seconds since midnight")
    
    @validator('end')
    def validate_time_window(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError('End time must be after start time')
        return v


class BreakTimeWindow(TimeWindow):
    """Time window for breaks with additional break-specific constraints."""
    max_duration: Optional[int] = Field(
        None,
        ge=0,
        le=86400,
        description="Maximum duration of the break in seconds"
    )
    min_duration: Optional[int] = Field(
        None,
        ge=0,
        le=86400,
        description="Minimum duration of the break in seconds"
    )
    
    @model_validator(mode='after')
    def validate_durations(self) -> 'BreakTimeWindow':
        if self.min_duration is not None and self.max_duration is not None and self.min_duration > self.max_duration:
            raise ValueError('min_duration cannot be greater than max_duration')
        return self

class VehicleBreak(BaseModel):
    """A break that must be taken by a vehicle during its route."""
    id: str
    duration: int = Field(..., gt=0, description="Duration of the break in seconds")
    time_windows: List[TimeWindow] = Field(
        default_factory=list,
        description="List of time windows when the break can be taken"
    )
    max_driving_duration_before_break: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum driving duration in seconds before this break must be taken"
    )

class VehicleCosts(BaseModel):
    """Cost factors for a vehicle."""
    fixed: float = Field(0.0, ge=0, description="Fixed cost per route")
    distance: float = Field(0.1, ge=0, description="Cost per meter")
    time: float = Field(0.05, ge=0, description="Cost per second")
    waiting: float = Field(0.02, ge=0, description="Cost per second of waiting time")
    break_time: float = Field(0.0, ge=0, description="Cost per second of break time")

class VehicleSkills(BaseModel):
    """Skills and capabilities of a vehicle."""
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

class JobRequirements(BaseModel):
    """Requirements that must be met to perform a job."""
    skills: List[str] = Field(
        default_factory=list,
        description="List of required skills to perform this job"
    )
    max_weight: Optional[float] = Field(
        None,
        ge=0,
        description="Maximum weight of the job in kg"
    )
    max_volume: Optional[float] = Field(
        None,
        ge=0,
        description="Maximum volume of the job in cubic meters"
    )
    required_licenses: List[str] = Field(
        default_factory=list,
        description="Required licenses to perform this job"
    )
    requires_hazardous: bool = False
    requires_refrigerated: bool = False

class LocationModel(BaseModel):
    """Geographic location with latitude and longitude."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lng: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    
    def to_tuple(self) -> Tuple[float, float]:
        """Convert to (lat, lng) tuple."""
        return (self.lat, self.lng)

class PlanningHorizon(BaseModel):
    """Time period over which to plan routes."""
    start_date: date
    end_date: date
    working_days: List[int] = Field(
        default_factory=lambda: list(range(5)),  # Monday to Friday by default
        description="List of working days (0=Monday, 6=Sunday)"
    )
    working_hours: Tuple[int, int] = Field(
        (9 * 3600, 17 * 3600),  # 9 AM to 5 PM by default
        description="Working hours as (start_seconds, end_seconds) since midnight"
    )
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v
    
    @validator('working_days')
    def validate_working_days(cls, v):
        if not all(0 <= day <= 6 for day in v):
            raise ValueError('Working days must be between 0 (Monday) and 6 (Sunday)')
        return sorted(set(v))  # Remove duplicates and sort
    
    @validator('working_hours')
    def validate_working_hours(cls, v):
        start, end = v
        if not (0 <= start < end <= 86400):
            raise ValueError('Invalid working hours. Must be between 00:00 and 24:00 with start < end')
        return v

class VehicleRequest(BaseModel):
    """Request model for a vehicle in route optimization."""
    id: str
    type: VehicleType = VehicleType.CAR
    start_location: LocationModel
    end_location: Optional[LocationModel] = None
    capacity: int = Field(1, ge=1, description="Capacity of the vehicle (number of jobs)")
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
    max_driving_duration: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum driving duration in seconds"
    )
    max_distance: Optional[float] = Field(
        None,
        gt=0,
        description="Maximum driving distance in meters"
    )

class JobRequest(BaseModel):
    """Request model for a job in route optimization."""
    id: str
    location: LocationModel
    duration: int = Field(
        300, 
        ge=0, 
        description="Service duration in seconds"
    )
    time_window: Optional[TimeWindow] = None
    priority: int = Field(
        1, 
        ge=1, 
        le=10, 
        description="Job priority (1-10, higher is more important)"
    )
    requirements: JobRequirements = Field(
        default_factory=JobRequirements,
        description="Requirements for performing this job"
    )

class RouteStep(BaseModel):
    """A single step in a route."""
    type: str  # 'start', 'job', 'break', 'end'
    location: LocationModel
    arrival_time: int  # seconds since midnight
    departure_time: int  # seconds since midnight
    distance: float  # meters
    waiting_time: int = 0  # seconds
    job_id: Optional[str] = None
    break_id: Optional[str] = None

class Route(BaseModel):
    """A route for a single vehicle on a single day."""
    vehicle_id: str
    date: date
    steps: List[RouteStep]
    total_distance: float  # meters
    total_duration: int  # seconds
    total_cost: float
    total_waiting_time: int = 0  # seconds
    total_break_time: int = 0  # seconds

class VehicleSchedule(BaseModel):
    """Represents a vehicle's schedule for a single day."""
    date: date
    start_time: time
    end_time: time
    breaks: List[VehicleBreak] = Field(
        default_factory=list,
        description="List of breaks for this vehicle on this day"
    )
    max_driving_duration: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum driving duration in seconds for this day"
    )
    max_distance: Optional[float] = Field(
        None,
        ge=0,
        description="Maximum driving distance in meters for this day"
    )
    assigned_jobs: List[JobRequest] = Field(
        default_factory=list,
        description="Jobs assigned to this vehicle on this day"
    )
    
    @property
    def working_duration(self) -> int:
        """Total working duration in seconds."""
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        if end <= start:
            end += timedelta(days=1)
        return int((end - start).total_seconds())
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }


class OptimizationRequest(BaseModel):
    """Request model for route optimization."""
    vehicles: List[VehicleRequest]
    jobs: List[JobRequest]
    optimization_type: OptimizationType = OptimizationType.DURATION
    planning_horizon: Optional[PlanningHorizon] = None
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional optimization options"
    )
    
    @validator('vehicles')
    def validate_vehicles(cls, v):
        if not v:
            raise ValueError('At least one vehicle must be provided')
        return v
    
    @validator('jobs')
    def validate_jobs(cls, v):
        if not v:
            raise ValueError('At least one job must be provided')
        return v


class OptimizationResult(BaseModel):
    """Result of a route optimization."""
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    routes: List[Route] = []
    total_distance: float = 0.0  # meters
    total_duration: int = 0  # seconds
    total_cost: float = 0.0
    optimization_type: OptimizationType = OptimizationType.DURATION
    metadata: Dict[str, Any] = {}
    errors: List[str] = []
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
        }
